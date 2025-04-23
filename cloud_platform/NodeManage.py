import time,socket
from abc import ABC, abstractmethod
from google.cloud import compute_v1
from collections import defaultdict
from kubernetes import client, config

from googleapiclient.errors import HttpError
from kubernetes.client import ApiException

from cluster.resources import Node
import logging, re, paramiko

logger = logging.getLogger(__name__)

class NodeManger(ABC):
    def __init__(self):
        self.instances = defaultdict()
        
    @abstractmethod
    def get_instances(self):
        pass

    @abstractmethod
    def refresh(self):
        pass


class GCP_Manager(NodeManger):
    def __init__(self,
                 project_id="single-cloud-ylxq",
                 region="australia-southeast1",
                 zone="b",
                 credential=None):
        super().__init__()
        self.project_id = project_id
        self.region = region
        self.zone = f"{self.region}-{zone}"
        self.instance_client = compute_v1.InstancesClient()

        self.no = 0

    def add_k8s_monitor(self, k8s_monitor):
        self.k8s_monitor = k8s_monitor

    def refresh(self):
        self.instances.clear()

        self.get_instances()

    def get_instances(self):
        logger.info("开始获取GCP平台下已经创建的机器")
        #time.sleep(2)
        try:
            request = compute_v1.ListInstancesRequest(
                project=self.project_id,
                zone=self.zone
            )
            response = self.instance_client.list(request)
            for instance in response:
                name = instance.name
                status = instance.status # 'TERMINATED' or 'RUNNING'
                type = instance.machine_type.split("/")[-1]
                internal_ip = list(instance.network_interfaces.pb)[0].network_i_p
                external_ip = list(list(instance.network_interfaces.pb)[0].access_configs)[0].nat_i_p
                info = {
                    "ExternalIP":external_ip,
                    "InternalIP":internal_ip,
                    "status": status,
                    'type':type,
                    'name':name
                }
                self.instances[name] = Node(name, info)
                #print(self.instances[name])
            return self.instances
        except Exception as e:
            logger.error(f"获取实例失败: {e}")
            raise

    def parse_node(self, node):
        pattern = re.compile(r'^node-(\d+)$')
        self.no = 0
        match = pattern.match(node.name)
        if match:
            index = int(match.group(1))
            self.no = index if index > self.no else self.no

    def create_node(self, node):
        name = f"node-{self.no + 1}"
        node.name = name
        self.no += 1
        type = node.type
        self.instance_client.insert(
            project=self.project_id,
            zone=self.zone,
            instance_resource=self._create_instance(name, type)
        )
        logger.info(f"创建实例{name},型号为{type}")
        if not self.wait_for_instance_ready(name):
            raise RuntimeError(f"实例 {name} 启动失败")
        node.internalIP, node.externalIP = self.get_instance_ip(name)
        time.sleep(5)
        self._ssh_connect(node)

    def get_instance_ip(self, name):
        logging.info(f"获取实例{name}的公网ip")
        instance = self.instance_client.get(
            project=self.project_id,
            zone=self.zone,
            instance=name
        )

        if instance.status =="RUNNING":
            network_interface = instance.network_interfaces[0]
            return (network_interface.network_i_p,network_interface.access_configs[0].nat_i_p)
        return None

    def wait_for_instance_ready(self, instance_name, timeout=600, interval=10):
        """等待实例进入RUNNING状态"""
        start_time = time.time()
        logger.info(f"开始等待实例 {instance_name} 初始化...")

        while time.time() - start_time < timeout:
            try:
                instance = self.instance_client.get(
                    project=self.project_id,
                    zone=self.zone,
                    instance=instance_name
                )

                if instance.status == "RUNNING":
                    logger.info(f"实例 {instance_name} 已进入运行状态")
                    return True
                elif instance.status == "TERMINATED":
                    logger.error(f"实例 {instance_name} 启动失败，状态为终止")
                    return False

                logger.debug(f"当前实例状态: {instance.status}，等待 {interval} 秒后重试...")
                time.sleep(interval)

            except HttpError as e:
                if e.resp.status == 404:
                    logger.debug(f"实例 {instance_name} 尚未创建完成，等待重试...")
                    time.sleep(interval)
                else:
                    logger.error(f"查询实例状态失败: {str(e)}")
                    raise

        logger.error(f"等待实例 {instance_name} 启动超时（{timeout}秒）")
        return False

    def _create_boot_disk(self):
        """创建启动磁盘配置"""
        initialize_params = compute_v1.AttachedDiskInitializeParams(
            source_image="projects/ubuntu-os-cloud/global/images/ubuntu-2204-jammy-v20250415",
            disk_size_gb=10,
        )
        return compute_v1.AttachedDisk(
            boot=True,
            auto_delete=True,
            initialize_params=initialize_params
        )

    def _create_network_interface(self) :
        """创建网络接口配置"""
        return compute_v1.NetworkInterface(
            subnetwork=f"projects/single-cloud-ylxq/regions/{self.region}/subnetworks/single-cloud-vpc",
            access_configs=[
                compute_v1.AccessConfig(
                    name="External NAT",
                    type="ONE_TO_ONE_NAT"
                )
            ],
            stack_type="IPV4_ONLY"
        )

    def _create_meta_data(self):
        return compute_v1.Metadata(
            items = [compute_v1.Items(
                key = "ssh-keys",
                value = f"root:ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKlKzCy4htWLghJGtK6W+ojkXEaQCZvxX4Me/sbPlpJG 13160@michael_win"
            )]
        )

    def _create_instance(self, name, type):
        return  compute_v1.Instance(
            name=name,
            machine_type = f"zones/{self.zone}/machineTypes/{type}",
            disks = [self._create_boot_disk()],
            network_interfaces = [self._create_network_interface()],
            metadata = self._create_meta_data(),
            service_accounts=[
                compute_v1.ServiceAccount(
                    email="883507821345-compute@developer.gserviceaccount.com",
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
            ]
        )

    def _ssh_connect(self, node):
        max_retries = 10  # 最大重试次数
        retry_interval = 5  # 重试间隔（秒）
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"尝试连接实例 {node.name}（第{attempt}次）IP: {node.externalIP}")
                ssh_client.connect(
                    hostname=node.externalIP,
                    username="root",
                    key_filename="./configurations/ssh_keys/kube-master-1-key",
                    look_for_keys=False,
                    timeout=20  # 连接超时设置为20秒
                )
                logger.info(f"成功连接到实例 {node.name}")
                break
            except Exception as e:
                if attempt == max_retries:
                    logger.error(f"连接失败已达最大重试次数{max_retries}次")
                    raise RuntimeError(f"无法连接到实例 {node.name}，错误详情：{str(e)}") from e
                logger.warning(f"连接失败（原因：{str(e)}），{retry_interval}秒后重试...")
                time.sleep(retry_interval)
                continue

        logging.info(f"连接到实例{node.name}")
        channel = ssh_client.invoke_shell()
        channel.settimeout(300)
        channel.send('echo "root:123456" | sudo chpasswd\n'.encode())
        self._wait_for_prompt(channel)

        # 2. 切换到root用户
        channel.send('sudo su -\n'.encode())

        # 处理可能的密码提示
        if not self._detect_root_prompt(channel):
            channel.send('123456\n'.encode())  # 发送sudo密码
            if not self._detect_root_prompt(channel, retries=10):
                raise Exception("切换到root用户失败")
        self._initialize_k8s_worker(ssh_client,node)

        return ssh_client

    def _detect_root_prompt(self, channel, retries=5):
        """检测root提示符"""
        output = ''
        for _ in range(retries):
            if channel.recv_ready():
                output += channel.recv(9999).decode()
            if '#' in output.split('\n')[-1]:  # 检测#提示符
                return True
            time.sleep(1)
        return False

    def _wait_for_prompt(self, channel, timeout=30):
        """等待命令提示符"""
        start = time.time()
        output = ''
        while time.time() - start < timeout:
            if channel.recv_ready():
                output += channel.recv(9999).decode()
                if any(prompt in output for prompt in ['$ ', '# ']):
                    return True
            time.sleep(0.5)
        return False

    def _initialize_k8s_worker(self, client, node):
        commands = [
            'export DEBIAN_FRONTEND=noninteractive',
            f'hostnamectl set-hostname {node.name}',
            'sudo modprobe overlay',
            'sudo modprobe br_netfilter',
            """cat <<EOF | sudo tee /etc/modules-load.d/kubernetes.conf
overlay
br_netfilter
EOF""".replace('"', '\\"'),
            """cat <<EOF | sudo tee /etc/sysctl.d/kubernetes.conf
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF""".replace('"', '\\"'),
            'sudo sysctl --system',
            "sudo apt-get install -y nfs-common rpcbind",
            "sudo timedatectl set-timezone Australia/Melbourne",
            "sudo apt update && sudo apt upgrade -y",
            "sudo mkdir -p /etc/apt/keyrings",
            "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg",
           'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null',
            "sudo apt-get update",
            "sudo apt-get install -y containerd.io",
            "sudo mkdir -p /etc/containerd",
            "containerd config default > /etc/containerd/config.toml",
            "sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml",
            "systemctl restart containerd",
            "systemctl enable containerd",
            "sudo apt-get update",
            "curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.32/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg",
            "echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.32/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list",
            "sudo apt-get update",
            "sudo apt-get install -y kubelet kubeadm kubectl",
            "sudo apt-mark hold kubelet kubeadm kubectl",
            "kubeadm join 10.152.0.4:6443 --token nfzjac.ip3yptkayzmspjs3 --discovery-token-ca-cert-hash sha256:5204c31dc557d21a76881656acda54c5b9f199e1696ab8776c187d8dbd56029f"
        ]
        for cmd in commands:
            self._execute_ssh_command(client, cmd)
        self._wait_node_ready_api(node.name)
        logger.info(f"{node.name}加入集群成功")

    def _wait_node_ready_api(self, node_name, timeout=600, interval=10):
        """通过K8s API监控节点状态"""
        start = time.time()
        last_observed_state = None
        logger.info(f"开始校验节点{node_name}是否加入集群")
        while time.time() - start < timeout:
            try:
                self.refresh()
                self.k8s_monitor.refresh()
                if (self.k8s_monitor.node_cache.get(node_name)) is None:
                    time.sleep(interval)
                    continue
                if (self.k8s_monitor.node_cache.get(node_name).status =="Ready"):
                    logger.info(f"节点 {node_name}就绪")
                    return

            except ApiException as e:
                if e.status == 404:
                    logger.debug(f"节点尚未注册: {node_name}")
                    time.sleep(interval)
                else:
                    logger.error(f"API请求失败: {e}")
                    raise
            except Exception as e:
                logger.error(f"未知错误: {str(e)}")
                raise

        raise RuntimeError(f"节点 {node_name} 未在{timeout}秒内就绪 | 最后状态: {last_observed_state}")

    def _execute_ssh_command(self, ssh_client, command, error_msg="命令执行失败"):
        """执行SSH命令并处理输出"""
        logger.debug(f"执行命令: {command}")
        stdin, stdout, stderr = ssh_client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()

        if exit_status != 0:
            error_output = stderr.read().decode().strip()
            logger.error(f"{error_msg}:\n{error_output}")
            raise Exception(f"{error_msg} (Exit code {exit_status}): {error_output}")

        # 记录命令输出
        output = stdout.read().decode().strip()
        if output:
            logger.debug(f"命令输出:\n{output}")
        return output
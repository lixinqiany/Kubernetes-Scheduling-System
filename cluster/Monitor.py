import logging
from kubernetes import config, client
from collections import defaultdict
from cluster.resources import Node, Pod
from cloud_platform.NodeManage import GCP_Manager
import os
logger = logging.getLogger(__name__)

class K8s_Monitor:
    def __init__(self, gcp_manager:GCP_Manager, credential=None):
        if credential is None:
            config.load_incluster_config()
        else:
            config.load_kube_config(credential)

        self.core_v1 = client.CoreV1Api()
        self.gcp_manager = gcp_manager
        self.node_cache = defaultdict()
        self.pod_cache = defaultdict()

    def refresh(self):
        self.node_cache.clear()
        self.pod_cache.clear()

        self.fetch_nodes()
        self.fetch_pods()
        self.allocate_pods()

    def fetch_nodes(self):
        try:
            nodes = self.core_v1.list_node().items
            for node in nodes:
                res = self._parse_node(node)
                if res is None:
                    continue
                k,v = res
                self.node_cache[k] = v
            logger.info(f"在Kubernetes集群中或得到了{len(self.node_cache)}个节点")
        except Exception as e:
            logger.info("错误发生在获取K8S节点时")
            print(e)
            raise

    def _parse_node(self, node):
        addresses = {x.type: x.address for x in node.status.addresses}
        status = "NotReady"
        for cond in node.status.conditions:
            if cond.type == "Ready":
                status = "Ready" if cond.status == "True" else "NotReady"
                if status == "NotReady":
                    return None
        e_ip = self.gcp_manager.instances[node.metadata.name].externalIP
        node_info = {
            "name": node.metadata.name,
            "InternalIP": addresses.get("InternalIP", None),
            "ExternalIP": e_ip,
            "Hostname": addresses.get("Hostname", None),
            "CPU": float(node.status.capacity["cpu"]),
            "RAM": self._parse_node_memory(node.status.capacity["memory"]),
            "status": status,
            "price":0
        }
        #logger.info(f"解析k8s Node ->\n\t{node_info}")
        return (node.metadata.name, Node(node.metadata.name, node_info))

    def _parse_node_memory(self, mem_str):
        if mem_str.endswith("Ki"):
            return float(mem_str[:-len("Ki")])/1024/1024
        return None

    def fetch_pods(self):
        try:
            pods = self.core_v1.list_pod_for_all_namespaces().items
            pods = [x for x in pods if x.metadata.namespace == "default"]
            for pod in pods:
                res = self._parse_pod(pod)
                if res is None:
                    continue
                k,v = res
                self.pod_cache[k] =v
            logger.info(f"在Kubernetes集群中得到了{len(self.pod_cache)}个Pods")
        except Exception as e:
            logger.info("错误发生在获取K8S pods时")
            print(e)
            raise

    def _parse_pod(self, pod):
        name, ns = pod.metadata.name, pod.metadata.namespace
        if pod.metadata.deletion_timestamp is not None:
            status = "Terminating"
        else:
            if pod.status.phase == "Pending" and pod.spec.node_name:
                status = "Scheduled"  # 已调度但未就绪
            else:
                status = pod.status.phase  # 保持原始状态
        node = pod.spec.node_name
        cpu = sum([self._parse_pod_cpu(x.resources.requests["cpu"]) for x in pod.spec.containers])
        ram = sum([self._parse_pod_ram(x.resources.requests["memory"]) for x in pod.spec.containers])
        pod_info = {
            "name": name,
            "namespace": ns,
            "status": status,
            "node": node,
            "CPU": cpu, "RAM": ram,
            "scheduler_name":pod.spec.scheduler_name
        }
        #logger.info(f"解析k8s Pod ->\n\t{pod_info}")
        pod_copy = Pod(pod_info)
        return (name, pod_copy)

    def _parse_pod_cpu(self, cpu):
        if cpu.endswith("m"):
            return float(cpu[:-len("m")])/1000
        else:
            return float(cpu)

    def _parse_pod_ram(self, ram):
        if ram.endswith("Gi"):
            return float(ram[:-len("Gi")])
        elif ram.endswith("Mi"):
            return float(ram[:-len("Mi")]) / 1024

    @property
    def pending_pods(self):
        return {k:v for k,v in self.pod_cache.items() if v.status == "Pending"}

    def allocate_pods(self):
        logger.info("开始将k8s内的节点和pod做匹配")
        pods = {k:v for k,v in self.pod_cache.items() if v.status=="Running"}
        for k,v in pods.items():
            node_name = v.node
            node = self.node_cache[node_name]
            node.pods.append(v)
            # logger.info(f"成功将{k}匹配到节点{node_name}")

if __name__=="__main__":
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "../configurations/single-cloud-ylxq-ed1608c43bb4.json"
    gcp_manager = GCP_Manager()
    a= K8s_Monitor(gcp_manager=gcp_manager,
        credential="../configurations/.kube/config")
    a.fetch_pods()
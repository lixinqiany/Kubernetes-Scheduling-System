from kubernetes.client import ApiException

from cluster.Monitor import K8s_Monitor
from cloud_platform.NodeManage import GCP_Manager
from cloud_platform.GCP_Pricing import GCP_Pricing
from optimizer.CABFD import CABFD
from kubernetes import client
import logging

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self,
                k8s_monitor: K8s_Monitor,
                gcp_manager:GCP_Manager,
                gcp_pricing:GCP_Pricing):
        self.k8s_monitor = k8s_monitor
        self.gcp_manager = gcp_manager
        self.gcp_pricing = gcp_pricing
        self.cabfd = CABFD(self.gcp_pricing)

    def _get_available_node(self):
        all_nodes = self.k8s_monitor.node_cache
        logger.info("调度器正在获取worker nodes")
        return [v for k,v in all_nodes.items() if v.name != "master" and v.status == "Ready"]

    def _get_pending_pod(self):
        logger.info("调度器正在获取pending pods")
        return [x for x in self.k8s_monitor.pending_pods.values() if x.scheduler_name=="custom-scheduling"]

    def schedule(self):
        logger.info("调度器开始调度")
        pendding_pods = self._get_pending_pod()
        nodes = self._get_available_node()
        logger.info("待调度pod如下：")
        _ = [logger.info(x) for x in pendding_pods]
        if nodes == []:
            logger.info("Kubernetes集群中暂无可用节点")
        else:
            logger.info(f"已有工作节点如下：")
            _ = [logger.info(x) for x in nodes]
        result = self.cabfd.optimize(pendding_pods, nodes.copy())
        self.cabfd.summary(result)

        logger.info("调度算法运行完毕！")
        return result

    def execute(self, plan):
        old_nodes = self._get_existing_node(plan)
        new_nodes = self._get_new_node(plan)

        for node in old_nodes:
            self.gcp_manager.parse_node(node)

        for node in new_nodes:
            self.gcp_manager.create_node(node)
        logger.info("调度方案中新节点安装完毕！")
        # 创建完新节点，刷新集群状态？
        for node in plan:
            pending_pods = [x for x in node.pods if x.status=="Pending"]
            for pod in pending_pods:
                if pod.node == None:
                    self._bind_pod(pod, node.name)

    def _get_existing_node(self, plan):
        return [x for x in plan if x.status=="Ready"]

    def _get_new_node(self,plan):
        return [x for x in plan if x.status == None]

    def _bind_pod(self, pod, node_name):
        api_instance = self.k8s_monitor.core_v1
        body = client.V1Binding(
            target=client.V1ObjectReference(
                kind="Node",
                api_version="v1",
                name=node_name
            ),
            metadata=client.V1ObjectMeta(name=pod.name, namespace=pod.namespace)
        )
        try:
            api_instance.create_namespaced_pod_binding(
                name=pod.name,
                namespace=pod.namespace,
                body=body
            )
            logger.info(f"绑定Pod {pod.name}到节点{node_name}成功")
        except ApiException as e:
            logger.error(f"绑定Pod {pod.name}到节点{node_name}失败")
            print(e)
        except Exception as e:
            logger.info(f"绑定Pod {pod.name}到节点{node_name}成功")
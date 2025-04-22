import time
from abc import ABC, abstractmethod
from google.cloud import compute_v1
from collections import defaultdict
from cluster.resources import Node
import logging

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

    def refresh(self):
        self.instances.clear()

        self.get_instances()

    def get_instances(self):
        logger.info("开始获取GCP平台下已经创建的机器")
        time.sleep(2)
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
                print(self.instances[name])
            return self.instances
        except Exception as e:
            logger.error(f"获取实例失败: {e}")
            raise
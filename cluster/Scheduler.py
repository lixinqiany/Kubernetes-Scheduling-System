from cluster.Monitor import K8s_Monitor
from cloud_platform.NodeManage import GCP_Manager
import logging

logger = logging.getLogger(__name__)

class Scheduler:
    def __int__(self, k8s_monitor: K8s_Monitor, gcp_manager:GCP_Manager):
        self.k8s_monitor = k8s_monitor
        self.gcp_manager = gcp_manager

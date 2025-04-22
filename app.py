from cloud_platform.GCP_Pricing import GCP_Pricing
from cloud_platform.AWS_Pricing import AWS_Pricing
from cloud_platform.NodeManage import GCP_Manager
from cluster.Monitor import K8s_Monitor
import logging, os, threading, warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

logging.basicConfig(
            level=logging.INFO,  # 设置全局日志级别（DEBUG及以上会记录）
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',  # 时间格式
        )

class System:
    def __init__(self, falvor_pool, pricing_json):
        self.gcp_pricing = GCP_Pricing(credential="./configurations/single-cloud-ylxq-ed1608c43bb4.json")
        self.aws_pricing = AWS_Pricing()
        self.flavor_pool = falvor_pool
        self.gcp_pricing.setup(self.flavor_pool)

        self.gcp_manager = GCP_Manager()

        self.k8s_monitor = K8s_Monitor(gcp_manager=self.gcp_manager,
                                       credential="./configurations/.kube/config")

        self.pricing_json = pricing_json

    def run(self):
        self.refresh(self.pricing_json, self.gcp_pricing, self.aws_pricing)

    def refresh(self, fp,
                gcp:GCP_Pricing,
                aws:AWS_Pricing,
                gcp_manager:GCP_Manager,
                k8s_monitor:K8s_Monitor):
        lock = threading.Lock()
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(gcp.refresh(fp, lock), name="gcp"): "gcp",
                       executor.submit(aws.refresh(fp, lock), name="aws"): "aws"}

            for future in as_completed(futures):
                logger.info(f"{futures[future]}刷新线程已完成！")
        gcp_manager.refresh()
        logger.info("GCP节点状态刷新完成！")
        k8s_monitor.refresh()
        logger.info("Kubernetes集群状态更新完成！")

if __name__=="__main__":
    system = System(falvor_pool="data/pre-defined-flavors.json",
                    pricing_json="data/pricing.json")
    system.run()
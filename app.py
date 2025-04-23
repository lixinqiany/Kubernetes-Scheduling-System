from cloud_platform.GCP_Pricing import GCP_Pricing
from cloud_platform.AWS_Pricing import AWS_Pricing
from cloud_platform.NodeManage import GCP_Manager
from cluster.Monitor import K8s_Monitor
from cluster.Scheduler import Scheduler
import logging, os, threading, warnings,time
from concurrent.futures import ThreadPoolExecutor, as_completed
from kubernetes import watch

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
        self.gcp_manager.add_k8s_monitor(self.k8s_monitor)

        self.scheduler = Scheduler(k8s_monitor=self.k8s_monitor,
                                   gcp_manager=self.gcp_manager,
                                   gcp_pricing=self.gcp_pricing)


        self.pricing_json = pricing_json
        self._running = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=2)


    def run(self):
        self._running.set()
        self.refresh_pricing()
        self.executor.submit(self._periodic_task_wrapper,
                             self.refresh_pricing,
                             600)

        self.executor.submit(self._monitor_pending_pods)

        logger.info("所有服务已启动")

    def _periodic_task_wrapper(self, func: callable, interval: int):
        """定时任务包装器"""
        while self._running.is_set():
            time.sleep(interval)
            try:
                func()
            except Exception as e:
                logger.error(f"定时任务执行失败: {str(e)}")

    def refresh_pricing(self):
        logger.info("开始刷新定价模型")
        lock = threading.Lock()
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {executor.submit(self.gcp_pricing.refresh(self.pricing_json, lock), name="gcp"): "gcp",
                           executor.submit(self.aws_pricing.refresh(self.pricing_json, lock), name="aws"): "aws"}

                for future in as_completed(futures):
                    logger.info(f"{futures[future]}定价刷新线程已完成！")
        except Exception as e:
            logger.error(f"主程序定价刷新出现故障")

    def refresh_cluster(self):
        logger.info("开始刷新节点状态")
        self.gcp_manager.refresh()
        logger.info("GCP节点状态刷新完成！")
        self.k8s_monitor.refresh()
        logger.info("Kubernetes集群状态更新完成！")

    def _monitor_pending_pods(self):
        """基于K8s Watch API的事件驱动监控"""
        logger.info("开始监听集群pods")
        while self._running.is_set():
            try:
                # 获取所有Pod并过滤Pending状态且使用自定义调度器的
                pods = self.k8s_monitor.core_v1.list_pod_for_all_namespaces().items
                pending_count = 0
                for pod in pods:
                    if pod.status.phase == "Pending" and pod.spec.scheduler_name == "custom-scheduling" and pod.metadata.namespace == "default":
                        pending_count += 1
                if pending_count > 0:
                    logger.warning(f"检测到{pending_count}个Pending Pod，触发调度")
                    self._trigger_emergency_scheduler()
                    time.sleep(10)
                else:
                    logger.info("当前没有Pending Pod")
                time.sleep(10)
            except Exception as e:
                logger.error(f"检查Pending Pod时出现错误: {str(e)}")
                time.sleep(5)  # 错误后等待5秒再重试
                raise


    def _trigger_emergency_scheduler(self):
        """紧急调度流程"""
        logger.info("触发调度...")
        self.refresh_cluster()
        self.refresh_cluster()
         # 执行调度
        self._trigger_scheduling()

    def _trigger_scheduling(self):
        """触发调度流程"""
        try:
            logger.info("开始调度流程...")
            result = self.scheduler.schedule()
            if result:
                self.scheduler.execute(result)
                logger.info("调度执行完成")
                self.refresh_cluster()
            else:
                logger.info("无需要调度的任务")
        except Exception as e:
            logger.error(f"调度执行失败: {str(e)}")
            raise

    def shutdown(self):
        """停止所有后台服务"""
        self._running.clear()
        self.executor.shutdown(wait=False)
        logger.info("系统服务已关闭")


if __name__=="__main__":
    system = System(falvor_pool="data/pre-defined-flavors.json",
                    pricing_json="data/pricing.json")
    try:
        system.run()
        while True:  # 保持主线程运行
            time.sleep(1)
    except KeyboardInterrupt:
        system.shutdown()
    finally:
        os._exit(1)  # 强制退出
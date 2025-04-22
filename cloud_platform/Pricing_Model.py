from abc import ABC, abstractmethod
from collections import defaultdict
import logging, json

logger = logging.getLogger(__name__)

class Pricing_Model(ABC):
    def __init__(self):
        self.machine_cache = defaultdict(list)
        self.pricing_cache = defaultdict(dict)
        self.machine2price_cache = defaultdict(dict)

    def _read_flavor_pool(self, fp, platform):
        """
        读取指定目录下关于指定平台的预定义机器范围
        """
        with open(fp, 'r') as fp:
            flavors = json.load(fp)[platform]
            logger.info(f"加载{platform}预定以机器池")
            return flavors

    @abstractmethod
    def export(self, fp):
        """
        导出对应的定价数据
        :return:
        """
        pass

    @abstractmethod
    def refresh(self, fp):
        """
        刷新GCP/AWS当前时刻的定价模型和可用机型，及对应的定价数据
        开机时执行一次refresh可以初始化
        :return:
        """
        pass

    @abstractmethod
    def fetch_pricing_model(self):
        """
        获取GCP/AWS对于Compute Engine的定价模块数据
        :return:
        """
        pass

    @abstractmethod
    def fetch_machine_types(self):
        pass

    @abstractmethod
    def calculate_pricing(self):
        pass
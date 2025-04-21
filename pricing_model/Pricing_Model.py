from abc import ABC, abstractmethod
from collections import defaultdict

class Pricing_Model(ABC):
    def __init__(self):
        self.machine_types = defaultdict(list)

    @abstractmethod
    def export(self):
        """
        导出对应的定价数据
        :return:
        """
        pass

    @abstractmethod
    def refresh(self):
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
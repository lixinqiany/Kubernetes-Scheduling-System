from collections import defaultdict
import logging, json

logger = logging.getLogger(__name__)

class AWS_Pricing():
    def __init__(self):
        pass

    def export(self, fp):
        """
        导出对应的定价数据
        :return:
        """
        pass

    def refresh(self, fp, lock):
        """
        刷新GCP/AWS当前时刻的定价模型和可用机型，及对应的定价数据
        开机时执行一次refresh可以初始化
        :return:
        """
        pass

    def fetch_pricing_model(self):
        """
        获取GCP/AWS对于Compute Engine的定价模块数据
        :return:
        """
        pass

    def fetch_machine_types(self):
        pass

    def calculate_pricing(self):
        pass
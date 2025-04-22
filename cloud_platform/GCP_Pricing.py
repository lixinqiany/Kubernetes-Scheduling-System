import json

from cloud_platform.Pricing_Model import Pricing_Model
from google.cloud import compute_v1, billing_v1
import os, logging,time

logger = logging.getLogger(__name__)

class GCP_Pricing(Pricing_Model):
    def __init__(self, project_id="single-cloud-ylxq",
                 region="australia-southeast1",
                 zone="b",
                 credential=None):
        super().__init__()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credential
        self.project_id = project_id
        self.region = region
        self.zone = f"{self.region}-{zone}"
        self.pre_defined_vm = []
        self.compute_client = compute_v1.MachineTypesClient()
        self.billing_client = billing_v1.CloudCatalogClient()

    def setup(self, fp):
        self.pre_defined_vm = self._read_flavor_pool(fp, "gcp")
        logger.info(f"GCP 定价模型配置完成")

    def refresh(self, fp, lock):
        self.machine_cache.clear()
        self.pricing_cache.clear()
        self.machine2price_cache.clear()

        self.fetch_machine_types()
        self.fetch_pricing_model()
        lock.acquire()
        self.calculate_pricing()
        self.export(fp)
        lock.release()

    def export(self, fp):
        temp = [{k:v} for k,v in self.machine2price_cache.items()]
        if os.path.isfile(fp):
            logger.info(f"刷新系统内GCP相关机器定价数据，文件目录{fp}")
            with open(fp, 'r') as f:
                data = json.load(f)
                aws = data.get('aws', {})
                res = {'gcp': temp,
                       'aws': aws}
            with open(fp, 'w') as f:
                json.dump(res, f)

        else:
            logger.info(f"初始化系统内的GCP相关机器定价数据，文件目录{fp}")
            with open(fp, 'w') as f:
                res = {'gcp': temp,
                       "aws":{}}
                json.dump(res, f)

    def fetch_pricing_model(self):
        logger.info("开始获取当前机型范围内所有定价模型")
        time.sleep(2)
        services = list(self.billing_client.list_services())
        self.compute_service_id = next(
            s.name for s in services
            if s.display_name == "Compute Engine"
        )
        skus = self.billing_client.list_skus(parent=self.compute_service_id)
        skus = [sku
                for sku in skus
                if sku.category.usage_type == "OnDemand" and
                self.region in sku.service_regions and
                ("Instance Core" in sku.description or "Instance Ram" in sku.description) and
                len(sku.description.split(" ")) <= 7]
        for sku in skus:
            entry = self._parse_sku(sku)
            if entry:
                self.pricing_cache[entry['id']][entry['resource']] = entry['price']
                print(f"\t{entry['id']}型号的{entry['resource']}报价={entry['price']:6f}每小时")

        return self.pricing_cache

    def _parse_sku(self, sku):
        """解析单个SKU的数据结构"""
        try:
            # 切分后第一个是类似“n4”, "c3"类似
            mt_id = sku.description.lower().split()[0]
            if self.machine_cache == {}:
                raise Exception("请先获取项目可用VM类型")
            else:
                if mt_id not in self.machine_cache.keys():
                    return None
            # 解析定价信息
            for tier in sku.pricing_info:
                pricing_expression = tier.pricing_expression

                for tier_rate in pricing_expression.tiered_rates:
                    price = tier_rate.unit_price
                    amount = price.nanos / 1e9

            return {
                "id": mt_id,
                "resource": sku.category.resource_group, # cpu or ram
                "price": amount
            }
        except Exception as e:
            logger.error(f"错误发生在解析sku数据")
            print(e)
            raise

    def fetch_machine_types(self):
        logger.info(f"开始Fetch GCP的{self.zone}下的所有可用机器类型")
        # 构建“列出所有可用机型“的请求body
        try:
            request = compute_v1.ListMachineTypesRequest(
                project=self.project_id,
                zone=self.zone
            )
            machines = self.compute_client.list(request)
            for mt in machines:
                if mt.name in self.pre_defined_vm:
                    info = {
                        "type": mt.name,
                        "CPU": mt.guest_cpus,
                        "RAM": mt.memory_mb
                    }
                    self.machine_cache[mt.name.split('-')[0]].append(info)
                    print(f"\t{info}")
        except Exception as e:
            logger.error(f"错误发生在获取GCP可用VM时")
            print(e)
            raise

        return self.machine_cache

    def calculate_pricing(self):
        logger.info("开始计算GCP平台当前可用机型的定价")
        time.sleep(5)
        try:
            for type, vms in self.machine_cache.items():
                cpu_p, ram_p = self.pricing_cache[type]['CPU'], self.pricing_cache[type]['RAM']
                for vm in vms:
                    vcpu, ram = vm['CPU'], vm['RAM'] / 1024
                    self.machine2price_cache[vm['type']] = {
                        "CPU": vcpu,
                        "RAM": ram,
                        "price": vcpu * cpu_p + ram_p * ram
                    }
                    print(f"\t{vm['type']}的价格为{vcpu * cpu_p + ram_p * ram:.6f}")
        except Exception as e:
            logger.error(f"错误发生在计算VM定价时")
            print(e)
            raise

        return self.machine2price_cache


if __name__=="__main__":
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "../configurations/single-cloud-ylxq-ed1608c43bb4.json"
    gcp = GCP_Pricing()
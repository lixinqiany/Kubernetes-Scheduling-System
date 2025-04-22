from cloud_platform.GCP_Pricing import GCP_Pricing
from cloud_platform.AWS_Pricing import AWS_Pricing
import logging, os, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

logging.basicConfig(
            level=logging.INFO,  # 设置全局日志级别（DEBUG及以上会记录）
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',  # 时间格式
        )

def main():
    gcp_pricing = GCP_Pricing(credential="./configurations/single-cloud-ylxq-ed1608c43bb4.json")
    aws_pricing = AWS_Pricing()
    gcp_pricing.setup("./data/pre-defined-flavors.json")
    refresh("./data/pricing.json", gcp_pricing, aws_pricing)
    #gcp_pricing.refresh("./data/pricing.json")


def refresh(fp, gcp, aws):
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(gcp.refresh(fp), name="gcp"):"gcp",
                   executor.submit(aws.refresh(fp), name="aws"):"aws"}

        for future in as_completed(futures):
            logger.info(f"{futures[future]}刷新线程已完成！")
if __name__=="__main__":
    main()
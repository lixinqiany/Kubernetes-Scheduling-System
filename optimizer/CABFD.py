from cluster.resources import Pod, Node
from cloud_platform.GCP_Pricing import GCP_Pricing
import logging, os, json

logger = logging.getLogger(__name__)

class CABFD:
    def __init__(self,
                 gcp_pricing:GCP_Pricing):
        self.gcp_pricing = gcp_pricing
        # self.aws_pricing = pricing['aws']

    def optimize(self, pods, nodes):
        sorted_pods = sorted(pods, key=lambda x:(-x.memory, -x.cpu))

        schedule = []+nodes
        for pod in sorted_pods:
            candidates = []
            candidates = self._find_in_existing_nodes(schedule, pod)
            candidates += self._find_possible_types(pod)
            best = self._find_best(candidates, pod)
            best.pods.append(pod)
            if best in schedule:
                continue
            schedule.append(best)
            #best.price = 0
            best.name="created"

        return schedule

    def summary(self, schedule):
        cnt = 0
        tot_price = 0
        for node in schedule:
            type = node.type
            price = node.price
            tot_price += price
            vcpu, ram = node.cpu, node.memory
            pods = [(pod.cpu, pod.memory) for pod in node.pods]
            if node.name == "created":
                cnt += 1
                logger.info(f"创建节点{cnt}, 类型为{type}, 价格为{price}, 配置为{vcpu} vCPU和{ram}G RAM"
                            f"\n\t 部署的pod为 {pods}"
                            f"\n\t 占用CPU{node.occupied_cpu}个, 占用Memory{node.occupied_memory}G"
                            f"\n\t CPU占用率{100 * node.occupied_cpu / vcpu:.2f}%, Memory占用率{100 * node.occupied_memory / ram:.2f}%")
            else:
                logger.info(f"调度节点{node.name}, 类型为{type}, 价格为{price}, 配置为{vcpu} vCPU和{ram}G RAM"
                         f"\n\t 部署的pod为 {pods}"
                         f"\n\t 占用CPU{node.occupied_cpu}个, 占用Memory{node.occupied_memory}G"
                         f"\n\t CPU占用率{100*node.occupied_cpu/vcpu:.2f}%, Memory占用率{100*node.occupied_memory/ram:.2f}%")
        logger.info(f"总价为{tot_price}")
    def _find_in_existing_nodes(self, nodes, pod):
        request_cpu, request_ram = pod.cpu, pod.memory

        return [n for n in nodes
                if n.available_cpu >= request_cpu and n.availbale_memory >= request_ram]

    def _find_possible_types(self, pod:Pod):
        cnt = 0
        result= []
        for name, x in self.gcp_pricing.machine2price_cache.items():
            if x["CPU"] >= pod.cpu and x["RAM"] >= pod.memory:
                x.update({"type": name})
                result.append(Node("not-created", x))
        return result

    def _find_best(self, nodes, pod):
        best = max(nodes, key=lambda x: self._score(x, pod, nodes))
        #print("+"*10)
        #for node in nodes:
        #    logging.info(f"当前 {node.name}={node.type} 得分 {self._score(node, pod, nodes)}")
        return best

    def _score(self, node:Node, pod:Pod, candidates):
        avai_cpu, avai_ram = node.available_cpu, node.availbale_memory
        ram_util = 1-(avai_cpu - pod.cpu)/node.cpu
        cpu_util = 1-(avai_ram - pod.memory)/node.memory
        if node.name == "created" or node.status=="Ready":
            price = 1 - (0)
        else:
            price = 1 - (node.price / max(x.price for x in candidates))
        return 1*ram_util + 1*cpu_util + 0.5 * price


if __name__=="__main__":
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "../configurations/single-cloud-ylxq-ed1608c43bb4.json"
    os.environ["GCP_PROJECT"] = "single-cloud-ylxq"  # 可选自定义项目变量
    cabfd = CABFD()
    request1 = {"CPU": 0.7, "RAM": 0.2}
    request2 = {"CPU": 1, "RAM": 0.7}
    request3 = {"CPU":0.1, "RAM": 1}
    request4 = {"CPU": 0.2, "RAM": 0.9}
    setup = [20,20,40,5]
    requests=[request1,request2,request3,request4]
    pods=[]
    for i, s in zip(setup, requests):
        for _ in range(i):
            pods.append(Pod(s))
    result = cabfd.optimize(pods)
    cabfd.summary(result)
class Pod:
    def __init__(self, request: dict, limit=None, name=None):
        self.request = request
        self.limit = limit if limit else request
        self.status = request.get("status", None)
        self.namespace = request.get("namespace",None)
        self.node = request.get("node", None)
        self.name = request.get("name", None)

    @property
    def cpu(self):
        return self.request["CPU"]

    @property
    def memory(self):
        return self.request["RAM"]

    def __str__(self):
        return (f"Pod is {self.name}"
                f"\n\t-> status:{self.status}"
                f"\n\t-> requested CPU: {self.cpu}"
                f"\n\t-> requested Memory: {self.memory}"
                f"\n\t-> depolyed on {self.node}")


class Node:
    def __init__(self, name, configuration, pods=None):
        self.name = name
        self.type = configuration.get("type", None)
        self.cpu = configuration.get("CPU", None)
        self.memory = configuration.get("RAM", None)
        self.price = configuration.get("price", None)
        self.pods = pods if pods else []
        self.status = configuration.get("status", None)
        self.internalIP = configuration.get("InternalIP", None)
        self.externalIP = configuration.get("ExternalIP", None)

    @property
    def available_cpu(self):
        return self.cpu - sum(x.cpu for x in self.pods)

    @property
    def availbale_memory(self):
        return self.memory - sum(x.memory for x in self.pods)

    @property
    def occupied_cpu(self):
        return sum(x.cpu for x in self.pods)

    @property
    def occupied_memory(self):
        return sum(x.memory for x in self.pods)

    def __str__(self):
        return (f"Node is {self.name}"
                f"\n\t type: {self.type}"
                f"\n\t-> status:{self.status}"
                f"\n\t-> CPU: {self.cpu}"
                f"\n\t-> Memory: {self.memory}"
                f"\n\t-> has pods {self.pods}")
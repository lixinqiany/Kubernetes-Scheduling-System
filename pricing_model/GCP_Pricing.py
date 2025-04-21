from pricing_model import Pricing_Model
import os

class GCP_Pricing(Pricing_Model):
    def __init__(self, project_id="single-cloud-ylxq",
                 region="australia-southeast1",
                 zone="b"):
        super().__init__()
        self.project_id = project_id
        self.region = region
        self.zone = f"{self.region}-{zone}"

    def refresh(self):
        pass

    def export(self):
        pass

    def fetch_pricing_model(self):
        pass

    def fetch_machine_types(self):
        pass

    def calculate_pricing(self):
        pass


if __name__=="__main__":
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "../configurations/single-cloud-ylxq-ed1608c43bb4.json"
    gcp = GCP_Pricing()
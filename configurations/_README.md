### 配置文件清单

##### Kubernetes集群config

- cluster下第一个变量替换为`insecure-skip-tls-verify: true`
- server下的IP每次启动gcp的master实例都需要更换至其动态IP（https://<GCP_Master>:6443）

##### GCP项目配置

- GCP对应项目下Service Account的Json密钥

##### SSH私钥

- 用于连接GCP实例的SSH连接
- 公钥在要在创建机器时候写入

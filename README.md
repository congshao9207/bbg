## Trans-parser流水处理平台
本项目基于flask，pandas等框架实现。
[flask大概介绍](https://www.cnblogs.com/franknihao/p/7118469.html)
[pandas exercises](https://github.com/guipsamora/pandas_exercises)



### Usage

1. 本地安装好git
2. 使用ssh-keygen生成好id_rsa.pub, [把里面的内容放到gitlab上的ssh key配置里](https://www.jianshu.com/p/4f5cb637eff7)
3. 运行`git@192.168.1.8:transformer/trans-parser.git` 把项目clone到你本地
4. [本地环境安装好python3.6的环境](https://www.anaconda.com/distribution/)请选择3.6版本
5. 到你的项目目录下运行 `pip install -r requirements.txt` 安装项目依赖的包

### 开发流程
使用gitflow分支管理策略

推荐使用pycharm进行开发


### 单元测试
1. [如何使用pycharm运行单元测试](https://blog.csdn.net/chenmozhe22/article/details/81700504)

* 使用faker和[faker2db](https://github.com/emirozer/fake2db)来构建测试数据

2. 安装python test插件

   ```shell
   pip3 install pytest~~~~
   ```

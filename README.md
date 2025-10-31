# 校友邦自动签到脚本

## 介绍
这是一个基于 Python 3 的开源自动签到脚本，专为校友邦类实习/签到平台设计。它支持自定义经纬度（模拟定位）提交签到，适用于需要位置参数的签到场景。该脚本适合用于学习、测试与个人自动化，但请务必遵守目标站点的服务条款与法律规定。

## 软件架构
本项目采用 Python 3 编写，主要功能包括配置读取、网络请求、设备模拟和签到逻辑。核心模块包括：
- 配置管理：读取和保存签到所需的配置信息。
- 网络请求：处理登录、获取签到计划、提交签到等网络操作。
- 设备模拟：生成模拟设备信息，用于伪装设备指纹。
- 签到逻辑：根据配置信息自动完成签到流程。

## 安装教程
1. 安装 Python 3.x（推荐使用 Python 3.6 或更高版本）。
2. 克隆本仓库到本地：
   ```bash
   git clone https://gitee.com/ckkk524334/sign-sign-in.git
   ```
3. 安装依赖库：
   ```bash
   pip install -r requirements.txt
   ```

## 使用说明
1. 配置文件 `config.json` 中填写签到所需的账号、密码、经纬度等信息。
2. 运行脚本：
   ```bash
   python sign_in.py
   ```
3. 脚本会自动完成登录、获取签到计划、提交签到等操作，并输出执行结果。

## 参与贡献
1. Fork 本仓库。
2. 创建新的功能分支（如 `feat-signin`）。
3. 提交您的代码改进或新增功能。
4. 创建 Pull Request，等待审核与合并。

## 特技
1. 使用多语言 `Readme_XXX.md` 文件支持国际化，如 `Readme_en.md` 和 `Readme_zh.md`。
2. 了解更多 Gitee 相关资源：
   - Gitee 官方博客: [blog.gitee.com](https://blog.gitee.com)
   - Gitee 探索页面: [https://gitee.com/explore](https://gitee.com/explore)
   - GVP（Gitee 最有价值开源项目）: [https://gitee.com/gvp](https://gitee.com/gvp)
   - Gitee 封面人物: [https://gitee.com/gitee-stars/](https://gitee.com/gitee-stars/)
3. Gitee 官方使用手册: [https://gitee.com/help](https://gitee.com/help)

## 许可证
本项目遵循 MIT 许可证，请在使用时遵守相关条款。
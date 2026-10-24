# 电视固件工坊

[打开在线选配](https://huhao0208.github.io/tcl-firmware-builder/) · [刷机说明](docs/FLASHING.md) · [构建边界](PRODUCT.md) · [第三方来源](SOURCES.md) · [验证记录](docs/VERIFICATION.md)

为 **TCL T800T11 / tc8000_ay30a2 / Android 11 / V178** 选择组件，使用 GitHub Actions 生成完整 U 盘刷机镜像。当前不支持其他板型、版本或 Recovery `update.zip`。

## 使用

1. 网页选择 Magisk / 原包、Aerial / 原桌面、广告管理、购物键、七项预装入口和安装策略。
2. 点击“在 GitHub 提交构建”，使用自己的 GitHub 账号在新请求页确认提交。网页不收集访问令牌。构建仅由带 `build-request` 标签的请求触发，该标签只有本仓库协作者能够保留；公开提交不会启动构建。
3. 在请求的机器人评论或网页任务查询中查看真实状态；完成后下载 Release 的 ZIP。
4. 解压、核对 SHA-256，按照刷机说明准备 U 盘。**ZIP 不能直接改名为 IMG。**

所有自定义组合为**尚未实刷候选**。云端校验检查镜像结构和内容，不能替代真机启动验证。刷机可能清空应用、账号和设置；保留原救砖包。

预装应用“精简”为 `pm uninstall -k --user 0`，保留原系统 APK。Aerial 替换默认 HOME 及原桌面活动入口，不删除原桌面整个系统包。安装策略仅允许列出的 HOME / ADB 安装规则，不关闭 SELinux 或 APK 签名检查；厂商云控可能覆盖策略。

## 构建与校验

静态网页直接部署在 GitHub Pages，无服务器、无网页 PAT。Issue 创建时的配置快照经有限枚举校验，可信默认分支脚本下载固定摘要输入，重建 boot 后验证：

- 原救砖包大小、SHA-256、AML v2 容器和 CRC；
- boot 内核与原 ramdisk 内容不变，仅新增首次启动 overlay；
- 只修改 boot_a、对应 VERIFY 和容器 CRC，其余字节不变；
- 全部分区 VERIFY、IMG / ZIP SHA-256。

成品 ZIP 包含固定名称 IMG、BUILD.json、SHA256SUMS、许可附件和中文刷机说明。公共 Release 保存成品，不依赖 Actions 临时产物保留期。相同配置与相同构建配方复用已校验成品：配方摘要只覆盖构建相关文件（固定输入清单、组件与脚本模板），不含提交 SHA，纯文档或网页改动不重建。编辑 Issue 不会更改创建时快照；维护者可通过工作流的 `issue_number` 显式重试当前请求内容。

```sh
python3 -m unittest discover -s tests -v
npm test
npm run check
python3 -m http.server 8765 --directory web
```

Linux x86_64 可本地构建（约需 12 GB 可用磁盘，无需 Android SDK）：

```sh
mkdir -p work
cp examples/default.json work/config.json
python3 scripts/build.py --config work/config.json --work work/build --output dist
```

运行器使用官方 Magisk 27 APK 内的静态 `magiskboot`，无需额外下载安装来历不明的固件工具。不要对成品运行首次启动脚本；这些脚本只供该板型开机执行。

## 项目结构

| 路径 | 用途 |
| --- | --- |
| web/ | 中文选配、草稿与任务查询 |
| catalog/inputs.json | 固定输入文件大小和摘要 |
| scripts/ | 严格配置、容器验证、打包和 GitHub 状态桥接 |
| templates/ | 一次性初始化和已知安装策略 |
| components/ | 公开基础广告规则模块 |
| .github/workflows/ | 检查、Pages 和构建工作流 |

仅构建器自有源码适用 MIT。TCL、Magisk、Aerial、字体等第三方内容保留各自许可，详见 SOURCES.md。现有私人维护仓库、签名密钥和个人电视数据不在本仓库中。

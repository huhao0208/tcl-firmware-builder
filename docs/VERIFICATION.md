# 验证记录 · 2026-10-24

## 云端完整构建

源码 `8de8303d397b868787ff5c56e72c7fb238c33bb4`。

- [任务 #2](https://github.com/huhao0208/tcl-firmware-builder/issues/2)、[成功运行](https://github.com/huhao0208/tcl-firmware-builder/actions/runs/40079854825)。
- 默认组合：Magisk 27、Aerial wb.11、CastGuard、购物键桥接、七项 user 0 入口移除、保留原厂安装策略。
- 官方 Magisk APK 内的静态 x86_64 magiskboot 在 GitHub Ubuntu 运行器成功解包/重包。
- 输入固定摘要、boot 原内核与原 ramdisk、新增 overlay 权限/内容、全部分区 VERIFY（该镜像共 15 项）、其余容器字节不变与 AML CRC 校验通过。
- [公开成品 Release](https://github.com/huhao0208/tcl-firmware-builder/releases/tag/build-d1f102b5d8d98eba)。
- ZIP 大小 `1929121750` 字节，SHA-256 `f27b1ba51b23840779d172b2f6c410a88c7bdb5238db7a93b90a0f5c0f01faa6`。
- IMG 大小 `2913239064` 字节，SHA-256 `78901b8c949eec7d075a99910e8b9045ea14eff30fb2bf34773f8612ba20e943`。
- 从公共下载 URL 下载完整 ZIP 回本机，核对 ZIP SHA-256、ZIP 内容 CRC、完整 IMG 大小/SHA-256、嵌入配置与固定名称，全部通过。

## 提交、复用与拒绝

- [任务 #4](https://github.com/huhao0208/tcl-firmware-builder/issues/4) 从实际生产网页打开预填 GitHub 确认页并确认创建。[运行](https://github.com/huhao0208/tcl-firmware-builder/actions/runs/40080175872) 验证已有 Release 摘要后复用，未重复下载组装底包。
- [任务 #3](https://github.com/huhao0208/tcl-firmware-builder/issues/3) 为故意提交 Root=false 但仍选扩展的负向测试；在配置阶段拒绝，未进入镜像构建，机器人及网页显示失败原因。该失败符合预期。
- 生产网页实际查询到构建中、构建完成、成品复用、配置拒绝、未知任务 404、非法编号错误和清空恢复；完成状态提供正确下载 URL。

## 本地与网页

7 项 Python 测试覆盖非法/重复输入、依赖、Issue 格式、八组组件 payload 的文件清单/权限/摘要和 shell 语法、cpio 边界、ZIP 固定名称与拒绝覆盖。5 项 Node 测试覆盖网页配置/确认 URL、任务编号、bot 和链接来源限制及畸形状态。JS 语法检查通过。

实际浏览器检查桌面与 390px 窄屏、原包禁用扩展、原桌面禁用购物键、批量选项、草稿保留、键盘提交、错误及状态恢复。严格 UI 审查零项发现，DESIGN.md 结构和运行时色值映射检查通过。无项目已有的离线自动化测试；网络失败与超时分支已实现，未把静态检查当作离线实测。

## 未验证范围

没有把此定制组合刷入电视。全新 /data 的首次安装、可选安装策略、wb.11 更新基线及每个选配组合的冷启动仍需独立真机验收。用户历史验证的是指定板型基础 Root、wb.10 电视功能与自更新；不能转移为新组合的实刷结论。未验证其他板型、固件、Recovery ZIP 或第三方账号的首次贡献审批状态。

私人维护仓库保持私有，既有稳定 APK 通道仍为 wb.10。公开候选包含已签名 APK，不包含私人签名密钥、私人规则及电视账号数据。

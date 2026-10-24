# 第三方来源

- 底包：TCL T800T11 V178 用户提供的救砖固件，仅声明指定板型兼容范围。构建器 MIT 许可不覆盖 TCL 固件。
- Magisk 27.0：https://github.com/topjohnwu/Magisk/tree/v27.0 ，GPL-3.0；APK 摘要固定，Linux x86_64 magiskboot 和 Android ARMv7 BusyBox 均从该 APK 提取。对应源码：https://github.com/topjohnwu/Magisk/archive/refs/tags/v27.0.tar.gz 。
- Aerial Workbench 1.41-wb.11：基于 https://github.com/pengchujin/aerial-tv v1.41 的独立发行，MIT。对应完整定制源码公开在 https://github.com/huhao0208/aerial-workbench/tree/source-wb11 ；后续开发分支为 workbench。APK 与签名摘要固定，含定制固件安装策略恢复适配；原 Aerial MIT 与 Inter OFL 许可随仓库保留。未将其候选适配当作实刷验证。
- CastGuard 1.1 / TCL Global Ad Hosts 3.0：huhao0208，管理 APK 摘要固定；模块源码在 components/castguard，默认仅三条投屏广告域名，不包含私人订阅和家庭配置。

版本、大小和完整 SHA-256 以 catalog/inputs.json 为准。输入不使用任意下载链接，也不读取私人维护仓库凭据。

## 许可范围

桌面运行时依赖、字体、图标和数据的独立协议见 AERIAL-THIRD-PARTY-NOTICES.txt。该文件含 69 项解析依赖的许可证、版权和原始 NOTICE，不将依赖统一改为 MIT。Magisk 保留 GPL-3.0；原 TCL 系统固件不属于 MIT 代码，公开构建器的许可不证明厂商固件的再分发授权。任何完整固件分发者仍需独立核对这部分权利。

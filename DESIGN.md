---
version: alpha
colors:
  primary: "#21726B"
  onPrimary: "#FFFFFF"
  text: "#152E36"
  surface: "#FFFFFF"
  background: "#F1F5F4"
  secondary: "#52676C"
  border: "#CDD9D7"
  warning: "#8A4F22"
  danger: "#A53630"
typography:
  display:
    fontFamily: "Arial, PingFang SC, sans-serif"
    fontSize: "44px"
  body:
    fontFamily: "system-ui, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "16px"
  caption:
    fontFamily: "SFMono-Regular, Consolas, monospace"
    fontSize: "12px"
rounded:
  control: "10px"
  panel: "20px"
spacing:
  page: "32px"
  gap: "24px"
components:
  button:
    backgroundColor: "#21726B"
    textColor: "#FFFFFF"
---

## Overview

中文电视固件配置工具，核心任务是准确选择组件、提交、追踪和下载。沿用客厅电视的视觉线索：右侧是一块窄边框电视与本次配置清单，左侧为可直接操作的原生表单。不是营销落地页。浅冷灰绿与深墨蓝配色，单一松绿行动色；只让电视预览成为视觉重点。

## Colors

Model B：web/theme.css 的语义 CSS 变量为唯一运行时来源，本文件镜像其值。主色用于提交、选中和焦点；警告文字用于未实刷及刷机数据影响，不用颜色独自传递状态。

## Typography

display 是 TV 标识与标题，body 是中文系统字体；caption 为配方和版本等技术信息的等宽字体。无远程字体加载，无持续动画。中文正文行高 1.65。

## Layout

桌面主区为 1fr / 340px 两列，配置清单可 sticky；手机回到单列自然文档滚动，动作在摘要内，不裁剪表单。最大宽度 1180px。任务查询在独立区域，与选配流程使用相同控件。

## Elevation & Depth

白色表单分组采用细边线；仅电视轮廓和配置摘要使用轻阴影。不使用全屏模糊和宣传型渐变。

## Shapes

控件 10px、面板 20px，电视边框 16px。原生 radio/checkbox 继续保持平台交互形状与键盘行为。

## Components

Form / validation：web/app.js 的 schema adapter，契约见 PRODUCT.md。Check/radio：原生带 label；没有自绘 select。Button：共享 .button；错误与任务反馈：共享 .notice / aria-live。CSS tokens → 控件和布局是唯一映射，不在 JS 复制颜色。开关依赖通过字段禁用状态、说明和摘要表达，生成配置时再次校验。

## Do's and Don'ts

提交按钮固定尺寸，加载和出错不挪动控件；错误关联字段并聚焦。日期使用 zh-CN / Asia/Shanghai，网络状态保留现有内容。所有外部结果只用文本渲染，链接验证来源；不接受网页令牌，不使用原生 alert/confirm。支持 focus-visible、reduced motion 和系统高对比度。

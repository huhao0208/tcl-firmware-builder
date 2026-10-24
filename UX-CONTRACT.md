# 网页行为契约

业务来源：PRODUCT.md，用户已批准公开构建器与定制固件下载。布局与视觉来源：DESIGN.md。

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
| --- | --- | --- | --- | --- |
| Form | web/config.js validate + web/app.js | web/catalog.json / PRODUCT.md | Native radio and checkbox; inline error | Dependencies, draft retention, first error focus |
| Select/Listbox | Native radio / checkbox | web/index.html + catalog | No authored select | Keyboard and labels |
| Scrollbar | web/theme.css global tokens | DESIGN.md | Standard and WebKit geometry | Desktop and mobile overflow |
| Toast | .notice + aria-live | web/app.js message | Persistent field errors, no toast-only errors | Network and recovery |
| CRUD | GitHub issue confirmation + task query | PRODUCT.md | Create in GitHub; read-only status | No issue created before confirmation |
| Async | loadTask AbortController | web/app.js | Timeout, manual retry, bounded polling | 404, rate limit, clear and cancellation |


网页选配可保留在本机；不记录任何账号、私人地址或 token。切换基础包会禁用不兼容组件，摘要忠实反映实际发出的配置；后端独立校验。创建请求在 GitHub 完成，使用用户自己的登录身份，不冒用维护者账号。

任务编号采用正整数并同步 URL。404、限流与断网为独立反馈；保留之前结果。只信任已知 bot 的状态块和固定仓库的链接。构建完成与实刷通过分开显示。没有匹配型号或来源时不给“兼容”承诺。

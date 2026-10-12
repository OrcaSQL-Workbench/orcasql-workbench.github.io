# OrcaSQL Workbench 文档与网站

本仓库用于维护 OrcaSQL Workbench 的公开用户文档与网站页面，并作为使用问题与文档反馈的统一入口。

## 内容与入口

- **[用户文档（GitHub Wiki）](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/wiki)**：入门指南、操作说明和常见问题。
- **[公开网站（GitHub Pages）](https://orcasql-workbench.github.io/)**：文档导航与问题反馈入口。
- **[隐私政策](https://orcasql-workbench.github.io/privacy/)**：适用于 OrcaSQL Workbench 0.1.0，生效日期为 2026年10月11日。
- **问题反馈（GitHub Issues）**：Workbench 使用问题与文档反馈。

用户文档与相关声明仍在准备中，发布后将在网站补充入口。

## 网站维护与发布

网站使用纯 HTML、CSS 和本地静态资源，不需要安装前端依赖。

- `site\index.html`：文档与支持首页。
- `site\privacy\index.html`：隐私政策。
- `site\assets\site.css`：首页与错误页样式。
- `.github\workflows\pages.yml`：静态验证与 GitHub Pages 自动发布。

本地检查：

```powershell
python scripts\validate_site.py
```

本地预览：

```powershell
python -m http.server 4178 --bind 127.0.0.1 --directory site
```

打开 `http://127.0.0.1:4178/`。正式站点使用组织根地址 `https://orcasql-workbench.github.io/`；404 页中的绝对链接从 `/` 开始，与本地预览一致。

PR 运行静态验证；合并到 `main` 后，通过 GitHub Actions 将 `site` 目录发布到 Pages。也可从 `main` 手动运行 `Publish website` 工作流。仓库的 Pages 发布来源应设为 **GitHub Actions**；工作流不会从 PR 或其他分支部署。

## 问题反馈

如遇到 Workbench 使用问题，或发现文档内容有误、缺漏或过时，请通过 [Issues](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/issues) 反馈。

请说明 Workbench 版本、问题现象和操作步骤。反馈中请勿包含账号凭据、客户数据或其他敏感信息。

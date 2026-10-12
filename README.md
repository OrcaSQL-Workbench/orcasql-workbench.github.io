# OrcaSQL Workbench 文档与网站

本仓库用于维护 OrcaSQL Workbench 的公开用户文档与网站页面，并作为使用问题与文档反馈的统一入口。

## 内容与入口

- **[用户文档（网站）](https://orcasql-workbench.github.io/docs/)**：入门指南、连接与 TLS、SQL 编辑执行、结果导出、历史与文件、常见问题。
- **[用户文档（GitHub Wiki）](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/wiki)**：同一份文档的单向自动同步镜像，首次使用需完成下述初始化和授权。
- **[公开网站（GitHub Pages）](https://orcasql-workbench.github.io/)**：文档导航与问题反馈入口。
- **[隐私政策](https://orcasql-workbench.github.io/privacy/)**：适用于 OrcaSQL Workbench 0.1.0，生效日期为 2026年10月11日。
- **问题反馈（GitHub Issues）**：Workbench 使用问题与文档反馈。

用户文档适用于 0.1.0；当前连接选择器提供 MySQL。相关声明和安装包下载入口尚未发布。

## 单一文档源

只在本仓库的 `docs` 目录维护正文，不直接编辑生成的网站文件或 Wiki。

- `docs\*.md`：用户文档 Markdown，第一行标题与导航标题一致。
- `docs\navigation.json`：网站和 Wiki 共用的页面顺序、标题及网站路径。
- `docs\assets`：两端共用的 PNG、JPEG、WebP 或 SVG 图片。
- `scripts\build_docs.py`：生成网站文档，或导出同样内容到 Wiki。
- `scripts\sync_wiki.py`：使用独立 Wiki 写入凭据，单向同步受管理的文件。

文档内部链接使用源文件名，例如 `Connections.md`；图片使用 `assets/图片名`。发布时转换为网站路径或 Wiki 页面路径。代码块与行内代码不作链接替换，不使用 Wiki 专属的 `[[页面]]` 语法。

生成的 `site\docs` 和 `.build` 不提交 Git。Wiki 镜像会保留自身 Git 历史，但直接修改受管理页面可能被下次同步覆盖；工具不会强制推送，也不会删除未受管理的 Wiki 页面。

## 网站维护与发布

网站使用纯 HTML、CSS 和本地静态资源，没有浏览器端 JavaScript。Markdown 文档使用固定版本的 Python 构建依赖。

- `site\index.html`：文档与支持首页。
- `site\privacy\index.html`：隐私政策。
- `site\assets\site.css`：首页与错误页样式。
- `.github\workflows\pages.yml`：文档构建、静态验证与 GitHub Pages 自动发布。
- `.github\workflows\wiki.yml`：主仓库文档到 GitHub Wiki 的单向同步。

本地检查：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-docs.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\build_docs.py --wiki-output .build\wiki
python scripts\validate_site.py
```

本地预览：

```powershell
python -m http.server 4178 --bind 127.0.0.1 --directory site
```

打开 `http://127.0.0.1:4178/`。正式站点使用组织根地址 `https://orcasql-workbench.github.io/`；404 页中的绝对链接从 `/` 开始，与本地预览一致。

PR 构建文档并运行校验；合并到 `main` 后，通过 GitHub Actions 将 `site` 目录发布到 Pages。也可从 `main` 手动运行 `Publish website` 工作流。仓库的 Pages 发布来源应设为 **GitHub Actions**；工作流不会从 PR 或其他分支部署。

## Wiki 初始化与写入授权

GitHub Wiki 使用独立的 `.wiki.git` 仓库，不会直接读取主仓库的 `docs`。

1. 在本仓库的 **Wiki** 页面创建并保存首个 `Home` 首页。临时占位内容会在首次同步时被文档源替换。
2. 准备一个能够写入该公共 Wiki 的专用、有限期令牌。公共 Wiki 通常使用 classic PAT 的 `public_repo` 授权；不要为了此用途授予私有仓库的完整 `repo` 权限，也不要默认认为 Actions 的 `GITHUB_TOKEN` 能写入 Wiki。
3. 在本仓库 **Settings → Secrets and variables → Actions** 中，由凭据持有者直接添加 `WIKI_SYNC_TOKEN`。令牌不得写入代码、文档、命令参数或聊天。
4. 从 `main` 运行 **Sync documentation Wiki**，或通过合并文档更改触发同步。

Wiki 初始化或授权缺失时，同步任务明确失败，不会将“未同步”报告为成功，也不会影响已经独立发布的网站。令牌过期或权限变化时，应在 Actions secrets 中更新后重新运行。

## 问题反馈

如遇到 Workbench 使用问题，或发现文档内容有误、缺漏或过时，请通过 [Issues](https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io/issues) 反馈。

请说明 Workbench 版本、问题现象和操作步骤。反馈中请勿包含账号凭据、客户数据或其他敏感信息。

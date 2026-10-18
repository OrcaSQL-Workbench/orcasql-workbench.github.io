# 维护者手册

## 修改文档

用户文档放在 `docs` 目录。网站和 Wiki 都从这里生成，修改内容时只改这一份。

- `docs\*.md`：文档正文。第一行标题要与导航中的标题一致。
- `docs\navigation.json`：页面顺序、标题和网站路径，网站与 Wiki 共用。
- `docs\assets`：文档图片，支持 PNG、JPEG、WebP 和 SVG。

文档之间的链接直接写源文件名，例如 `Connections.md`；图片路径写成 `assets/图片名`。发布时，脚本会转换为网站或 Wiki 对应的链接。代码块和行内代码中的内容不会转换。

不要使用 Wiki 专属的 `[[页面]]` 链接语法，也不要直接修改生成的 `site\docs` 或 Wiki 页面，以免被下次同步覆盖。

用户指南不标注固定的适用版本，但要写清楚当前支持的功能。反馈问题时，仍需提供实际使用的 Workbench 版本。

`site\docs` 和 `.build` 都是生成内容，不提交 Git。

## 修改网站

网站使用 HTML、CSS 和本地静态资源，不使用浏览器端 JavaScript。

- `site\index.html`：网站首页。
- `site\privacy\index.html`：隐私政策。
- `site\assets\site.css`：首页和错误页样式。
- `site\assets\privacy.css`：隐私政策页面样式。

正式地址是 `https://orcasql-workbench.github.io/`。网站部署在组织根路径 `/`，不是仓库名下面。站内绝对链接从 `/` 开始，404 页的资源链接和返回首页链接也一样。

## 本地检查

在仓库根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-docs.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\build_docs.py --wiki-output .build\wiki
python scripts\validate_site.py
```

`build_docs.py` 负责生成网站文档和导出 Wiki 文件，`validate_site.py` 负责检查静态页面。

## 本地预览

构建完成后，在仓库根目录启动预览：

```powershell
python -m http.server 4178 --bind 127.0.0.1 --directory site
```

打开 `http://127.0.0.1:4178/`。

## 发布网站

仓库的 Pages 发布来源要设为 **GitHub Actions**。

涉及网站或文档的 PR 会运行构建和检查。合并到 `main` 后，`Publish website` 工作流会自动发布 `site` 目录。需要重新发布时，也可以从 `main` 手动运行。

工作流文件是 `.github\workflows\pages.yml`，只发布 `main` 分支的内容。

## 配置 Wiki 同步

GitHub Wiki 有独立的 `.wiki.git` 仓库，不会直接读取主仓库的 `docs`。`scripts\sync_wiki.py` 负责把文档同步过去，第一次使用前需要完成以下设置。

1. 打开本仓库的 **Wiki**，创建并保存 `Home` 首页。先写占位内容即可，首次同步时会替换为文档首页。
2. 准备一个专用于 Wiki 同步、有到期时间的令牌。公共 Wiki 通常使用 classic PAT 的 `public_repo` 权限，不要为此授予可访问私有仓库的完整 `repo` 权限，也不要假定默认的 `GITHUB_TOKEN` 能写入 Wiki。
3. 由令牌持有者在 **Settings → Secrets and variables → Actions** 中添加 `WIKI_SYNC_TOKEN`。令牌只放在 Secrets 中，不要写进代码、文档、命令参数或聊天。
4. 从 `main` 手动运行 **Sync documentation Wiki**。

设置完成后，文档更改合并到 `main` 就会自动同步。工作流文件是 `.github\workflows\wiki.yml`。

Wiki 只是文档镜像。直接在 Wiki 修改由脚本管理的页面，下次同步可能会覆盖这些修改。脚本会保留 Wiki 的 Git 历史，不会强制推送，也不会删除它未管理的页面。

## Wiki 同步失败时

先检查 Wiki 是否已保存过首页，再检查 `WIKI_SYNC_TOKEN` 是否已配置、是否过期，以及是否有写入权限。

需要更换令牌时，由令牌持有者更新 Actions Secrets，然后重新运行同步工作流。缺少初始化或授权时，任务会报错，不会跳过同步后显示成功。

Wiki 同步与网站发布是两个独立工作流，Wiki 同步失败不影响网站发布。

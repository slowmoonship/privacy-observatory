# GitHub Pages 发布指南（尚未授权）

当前工作流只生成 Pages artifact，不含 deploy 步骤，也不会公开部署。用户已在普通 SSH 中初始化 Git；本环境可读到 main 分支、无提交及无远程，但 `.git` 只读，首次提交仍须在可写环境完成。

1. 在取得用户明确授权后，将经审查的代码和允许非商业再分发的快照提交并推送到用户指定的现有远程；不得擅自创建公开仓库。确认仓库 Actions 可用、工作流对内容有写权限及默认分支允许 `GITHUB_TOKEN` 推送；受保护分支可能需要采用经批准的替代方案。禁止使用 PAT 作为默认绕过方法。
2. 先手动运行 workflow_dispatch，检查 GitHub Runner 的三个数据组状态 artifact、日志、必要时数据提交、Pages artifact、失败场景及构建结果。随后再次单独手动触发一次，核对第二次全新 Runner 的 checkout 含第一次已提交的快照；对照两次状态 artifact、提交记录和三组数据。可在第一次采集后模拟单源失败，确认第二次 Runner 从仓库保留该组快照并更新其他组；不得将模拟结果说成真实上游故障。此在线验证目前未执行。
3. 正式发布经用户另行授权后，在 Settings → Pages 选择 GitHub Actions，并在同一工作流增加依赖 update 的部署 job：仅该 job 设置 `pages: write`、`id-token: write`，配置 `github-pages` environment 和 `actions/deploy-pages`。配置环境保护规则，确保仅允许默认分支并按需要要求人工审批。上线前重核来源许可、署名、非商业限制。
4. 项目站使用 `/<repository>/` 的 Vite base；工作流按仓库名构建。若使用用户站或自定义域名，改为 `/` 并重新验收。检查实际 Pages 链接、JSON 请求、刷新、桌面与移动端后再记录结果。

无 push 事件触发器；定时与手动运行只在默认分支执行，不依赖数据提交触发另一个工作流。部署与数据更新在授权后仍应属于同一条受控流水线；部署失败不得谎报发布成功。

# 修改与贡献

修改前先阅读 README 和 docs/PROVENANCE.md。贡献者须确认有权提交自己的代码及素材；本项目未自动授予通用开源许可。

1. 用独立分支完成一项改动，避免把不同目标混在一次提交中。
2. 使用合成样例，并为修复的计算问题添加回归测试。
3. 执行 `python -m unittest discover -s tests -v` 与 `python demo.py --no-chart`。
4. 用 `git diff`、`git diff --cached` 检查内容，不提交密钥、真实销售数据或未经授权的文档。
5. 更新 CHANGELOG；提交说明描述实际变化，不写未验证的效果提升。

如需生成新的文档演示图，运行 `python demo.py --output-dir docs/assets`，核对图表和数据均可公开后再提交。日常运行请保持默认 `outputs/`。

测试使用标准库 unittest。真实 API／Redis 的集成演示应由维护者在自己的账号环境中单独执行，避免在公共 CI 中放入密钥。

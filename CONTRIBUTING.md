# 贡献指南 (Contributing Guide)

欢迎为 **YSM AI Engine** 提交代码、文档改进、渲染优化或新的 YSM 角色示例！

## 一、快速提交流程

1. 点击仓库右上角 **Fork**，将项目复刻到你的 GitHub 账号下。
2. 克隆你的仓库并创建功能分支：
   ```bash
   git clone https://github.com/<你的用户名>/ysm-ai-engine.git
   cd ysm-ai-engine
   pip install -e .
   git checkout -b feat/your-feature-name
   ```
3. 完成开发后，在本地运行全套自动化测试确保全部通过：
   ```bash
   python -m unittest discover -s tests -v
   ```
4. 如果你新增或修改了角色示例，请确保通过 YSM 2.6.0 合规校验（必须 `0 errors`）：
   ```bash
   ysm-validate path/to/your_model_dir
   ```
5. 推送分支并发起 **Pull Request (PR)**：
   - 简要说明改动内容与动机；
   - 如涉及渲染器、WebGL2 预览器或示例模型改动，建议附上效果对比截图。

## 二、代码与仓库规范

- **保持零重型依赖**：核心引擎尽量仅依赖 `numpy` 与 `pillow`（前端预览器保持零构建依赖）。
- **不要提交大体积构建产物**：`out/`、`dist/`、`renders/`、`*.zip`、`*.bbmodel` 已在 `.gitignore` 中排除；示例工程请提交可复现的源码脚本（`build_model.py` / `build_animations.py` / `run_all.py`）。
- **保持 UTF-8 无 BOM 编码**，确保生成的 Bedrock JSON 与 YSM 2.6.0 规范完全兼容。

非常感谢你的每一次贡献！PR 合并后，你的 GitHub 账号会自动出现在仓库的 Contributors 列表中。

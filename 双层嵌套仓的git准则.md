# 双层嵌套仓的git准则

> 适用场景：  
> 外层主仓（如 `coco-ba-agent`） + 内层前端独立仓（如 `coco-frontend`）。  
> 目标：避免嵌套仓混乱、保证同步可追溯、降低协作风险。

---

## 1. 结构定义

- **外层仓**：主业务仓（后端、部署、文档、集成逻辑）
- **内层仓**：前端独立仓（来自公司前端平台分支）
- **推荐管理方式**：`git submodule`（子模块）

---

## 2. 核心原则（必须遵守）

1. 前端代码在内层仓提交，后端代码在外层仓提交。
2. 外层仓不直接“吞并”前端源码（除非明确改为 subtree/vendor 方案）。
3. 外层仓仅记录内层仓的版本指针（submodule commit）。
4. 每次更新前端后，外层仓需要提交一次“子模块指针更新”。
5. 不在外层仓执行无差别 `git add .`（容易误收嵌套仓状态）。

---

## 3. 一次性初始化（推荐）

```bash
cd /Users/yeziyu/Desktop/coco-ba-agent
git rm -r --cached coco-frontend
git submodule add -b temp/ai-126572bc ssh://git@git.sankuai.com/nocode/nocode-f01e49747abd4ef8.git coco-frontend
git add .gitmodules coco-frontend
git commit -m "chore: add coco-frontend as submodule"
git push origin master
```

---

## 4. 日常同步前端（标准流程）

### 4.1 在内层仓更新前端代码

```bash
cd /Users/yeziyu/Desktop/coco-ba-agent/coco-frontend
git fetch origin
git checkout temp/ai-126572bc
git pull origin temp/ai-126572bc
```

### 4.2 回到外层仓提交“指针更新”

```bash
cd /Users/yeziyu/Desktop/coco-ba-agent
git add coco-frontend
git commit -m "chore: bump coco-frontend submodule"
git push origin master
```

---

## 5. 新同学克隆项目后的正确初始化

```bash
git clone <outer-repo-url>
cd coco-ba-agent
git submodule update --init --recursive
```

更新时：

```bash
git pull
git submodule update --init --recursive
```

---

## 6. 一键拉子模块最新（可选）

```bash
cd /Users/yeziyu/Desktop/coco-ba-agent
git submodule update --remote --merge coco-frontend
git add coco-frontend
git commit -m "chore: update coco-frontend submodule"
git push origin master
```

---

## 7. 常见错误与处理

### 错误 1：`warning: adding embedded git repository`

**原因**：把内层独立仓当普通目录 add 到外层。  
**处理**：

```bash
git rm --cached -r coco-frontend
# 然后按子模块方式重新接入
```

### 错误 2：协作者 clone 后没有前端代码

**原因**：未初始化子模块。  
**处理**：

```bash
git submodule update --init --recursive
```

### 错误 3：前端更新了但外层看不到变化

**原因**：外层未提交子模块新指针。  
**处理**：

```bash
git add coco-frontend
git commit -m "chore: bump submodule pointer"
```

---

## 8. 提交规范建议

- **前端改动提交信息（内层仓）**
  - `feat: xxx`
  - `fix: xxx`
- **外层仓指针更新提交信息**
  - `chore: bump coco-frontend submodule to <short-sha>`

---

## 9. 上线前检查清单

- [ ] 内层仓前端改动已提交并推送
- [ ] 外层仓已提交子模块指针更新
- [ ] 外层仓 README 写明子模块初始化命令
- [ ] CI/CD 能正确拉取子模块（若开启）

---

## 10. 维护建议

- 固定一个前端上游分支（如 `temp/ai-126572bc`）
- 每次同步后做一次联调检查：
  - 前端启动
  - 聊天接口可调用
  - SSO 行为符合预期
- 如需长期“单仓一键克隆可运行”，可评估改用 `git subtree`

---

> 结论：  
> 双层嵌套仓可行，但必须“前端在前端仓提交、外层只提交指针”。

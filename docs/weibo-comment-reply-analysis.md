# 微博评论与回复机制深度分析

> 基于2026年4月实际抓包调试形成的技术文档，用于指导回复模块的正确实现。

---

## 一、微博评论体系结构

### 1.1 评论层级

微博的评论是**两级结构**（不是无限嵌套）：

```
微博帖子 (weibo_mid = 5282691010266961)
├── 根评论A (comment_id = 5284025771492373, user = 泡泡机灵豆)
│   ├── 子评论A1 (comment_id = ?, user = 小鹿乱撞1I, text = "你说呢")
│   ├── 子评论A2 (comment_id = ?, user = 其他人)
│   └── 子评论A3 (comment_id = ?, user = 泡泡机灵豆, text = "回复@小鹿乱撞1I:...")
├── 根评论B (comment_id = 5283308666881785, user = 泡泡机灵豆)
└── 根评论C (comment_id = 5282691119579761, user = 泡泡机灵豆)
```

**关键规则：**
- 所有"回复"都挂在根评论下面，视觉上呈现为"楼中楼"
- 即使子评论A3回复的是子评论A1，它依然挂在根评论A下
- 不存在第三级评论，任何回复都只能挂到二级

### 1.2 评论ID体系

每条评论（无论根评论还是子评论）都有一个唯一的数字ID，如 `5284025771492373`。这个ID：
- 是雪花算法生成的，数字本身包含时间信息（越大越新）
- 在回复API中作为 `cid` 或 `reply_id` 使用
- 与微博的 `mid`（帖子ID）是独立的命名空间

---

## 二、收件箱页面的URL参数

### 2.1 收件箱页面

URL: `https://www.weibo.com/comment/inbox`

每条评论卡片底部有一个时间链接，格式为：
```
https://weibo.com/{poster_uid}/{bid}?cid={cid}&rid={rid}
```

### 2.2 两种场景的URL参数

#### 场景一：楼中楼回复（有 cid + rid）

```
https://weibo.com/7764254452/Q8FJA2zsa?cid=5220676648567472&rid=5284012063990667
```

含义：
- `cid=5220676648567472` → **我方的根评论ID**（即我发的那条根评论）
- `rid=5284012063990667` → **对方的回复评论ID**（对方在我根评论下的具体回复）

这种场景下 `rid` 就是对方评论的真实ID，参数是完整的。

#### 场景二：直接评论（只有 cid，没有 rid）

```
https://weibo.com/5596465683/QyHaB17rP?cid=5284025771492373
```

含义：
- `cid=5284025771492373` → **我方的根评论ID**（注意：不是对方的评论ID！）
- 没有 `rid` → **对方的评论ID在URL中不存在**

> **这是导致回复错位的根本原因。** 当收件箱没有 `rid` 时，`cid` 实际上是"我自己的根评论"，而不是"对方回复我的那条评论"。对方的真实评论ID在URL中完全缺失。

### 2.3 两种场景的本质区别

| | 楼中楼（有rid） | 直接评论（无rid） |
|---|---|---|
| 场景 | 对方回复了我根评论下的某条子评论 | 对方直接回复了我的根评论 |
| cid含义 | 我的根评论ID | 我的根评论ID |
| rid含义 | 对方的回复评论ID | 不存在 |
| 对方评论ID | = rid ✓ | **URL中没有** ✗ |

---

## 三、回复API参数

### 3.1 API端点

```
POST https://www.weibo.com/ajax/comments/reply
Content-Type: application/x-www-form-urlencoded
```

### 3.2 我们代码发送的参数（旧方式，有问题）

`reply_sender.py` 的做法：

```python
# 楼中楼
params = "id={weibo_mid}&cid={root_comment_id}&reply_id={comment_id}&comment=..."

# 直接评论
params = "id={weibo_mid}&cid={comment_id}&reply_id={comment_id}&comment=..."
```

问题：
1. "直接评论"场景下，`comment_id` 来自inbox的 `cid`，实际是**我自己的根评论ID**
2. 用自己的根评论ID作为 `cid` 和 `reply_id`，结果是回复挂到了根评论下面（而不是对方的具体评论下面）
3. 即使"楼中楼"场景的参数看似正确，`cid + reply_id` 的组合也不一定能精确定位

### 3.3 微博前端UI实际发送的参数（正确方式）

通过AJAX拦截器捕获到，当我们在收件箱页面点击"回复"按钮 → 弹出输入框 → 输入文字 → 点击发送后，前端实际发送：

```
POST /ajax/comments/reply
body: id=5220670540612942&cid=5284131541882805&comment=footer回复测试9578
      &pic_id=&is_repost=0&comment_ori=0&is_comment=0
```

**关键发现：**
1. **没有 `reply_id` 参数** — 前端只用 `id` + `cid` + `comment`
2. **`cid` 是对方评论的真实ID** — 不是inbox URL里的 cid，而是前端从组件内部状态获取的真实评论ID
3. `id` 是微博帖子的MID（数字形式）

### 3.4 隐藏的评论ID — 前端如何获取

这是最关键的发现：**inbox URL中没有暴露的"对方评论ID"，实际存在于前端组件的内部数据中**。

当用户点击收件箱卡片底部的"回复"按钮时：
- 前端框架（Vue/React）从卡片组件的 props/state 中读取正确的评论ID
- 这个ID被传递给回复弹窗组件
- 弹窗组件用这个ID作为 `cid` 发送API请求

我们通过HTML解析拿不到这个ID，但通过**模拟UI点击**可以让前端帮我们处理。

---

## 四、子评论API的异常行为

### 4.1 buildComments API

理论上可以通过API获取根评论下的子评论：

```
GET /ajax/statuses/buildComments?is_reload=1&id={weibo_mid}
    &is_show_bulletin=2&is_mix=1&fetch_level=1
    &max_id=0&count=100&cid={root_comment_id}
```

### 4.2 实测结果：返回空

尽管根评论显示有3条回复（`total_number: 3`），但子评论API返回0条数据。

尝试了以下参数组合，全部返回空：
- `is_mix=1` / `is_mix=0`
- `flow=1`
- `id=cid`（用根评论ID替代微博ID）
- `/ajax/comment/detail` 端点

可能原因：
- 微博对子评论API有权限或频率限制
- 某些评论可能被折叠或隐藏
- API参数在近期版本中有变化

**结论：通过API查找子评论的方式不可靠，不能作为获取"对方评论ID"的手段。**

---

## 五、旧代码的Bug分析

### 5.1 parser.py 中的ID解析

```python
# parser.py _extract_comment_from_card()
cid_match = re.search(r"cid=(\d+)", href)
root_cid = cid_match.group(1) if cid_match else ""
rid_match = re.search(r"rid=(\d+)", href)

if rid_match:
    comment["comment_id"] = rid_match.group(1)   # ✓ rid = 对方评论ID
    comment["root_comment_id"] = root_cid          # ✓ cid = 我的根评论ID
else:
    comment["comment_id"] = root_cid               # ✗ BUG: cid 是我的根评论ID，不是对方的！
    comment["root_comment_id"] = None
```

### 5.2 reply_sender.py 中的参数构造

```python
# 直接评论（无rid时）
safe_cid = str(comment_id)      # comment_id = 我的根评论ID（错误）
safe_reply_id = safe_cid         # reply_id 也是我的根评论ID（错误）
```

结果：回复被挂到我自己的根评论下面作为新的子评论，而不是回复对方的那条具体评论。

### 5.3 reply_user_name 被忽略

`run_reply.py` 传入了 `reply_user_name` 参数：
```python
send_reply(..., reply_user_name=comment_user if root_comment_id else None)
```

但 `send_reply()` 用 `**_kwargs` 吞掉了这个参数，从未使用。即使使用了，通过"回复@xxx:"前缀也只是文本层面的引用，不能改变API层面的回复位置。

---

## 六、正确的解决方案：UI模拟回复

### 6.1 方案原理

不再自己构造API参数，而是**在收件箱页面模拟用户的真实操作**：

1. 访问 `https://www.weibo.com/comment/inbox`
2. 找到目标评论卡片
3. 点击卡片底部 `<footer>` 里的"回复"按钮（带 `_commentIcon_` 图标的那个）
4. 等待弹窗出现（弹窗标题会显示"回复 @某某某"，确认目标正确）
5. 在弹窗的 `<textarea>` 中输入回复内容
6. 点击弹窗中的"回复"按钮
7. 等待发送完成

### 6.2 关键CSS选择器

```
回复按钮入口: card内 i[class*="_commentIcon_"] 的最近 [class*="_wrap_"] 祖先
弹窗textarea: textarea (placeholder="发布你的回复")
发送按钮: button (text="回复" 且 class含"_btn_")
```

### 6.3 优势

- **前端自动处理正确的评论ID** — 不需要我们知道对方的真实评论ID
- **不需要区分"直接评论"和"楼中楼"** — 统一流程
- **不需要查询子评论API** — 绕过API返回空的问题
- **参数永远正确** — 和用户手动回复完全一致

### 6.4 风险和注意事项

- 页面CSS类名可能随版本更新变化（带hash的类名如 `_commentIcon_j8div_129`）
- 需要稳健的元素等待和错误处理
- 弹窗动画可能需要适当等待
- textarea 输入需要用 Selenium 原生方式（`send_keys`）才能触发React的状态更新

---

## 七、测试验证记录

### 7.1 UI回复测试（2026-04-06）

- 点击 `_wrap_` 层成功打开回复弹窗
- 弹窗标题："回复 @小鹿乱撞1I"（目标正确）
- Selenium `send_keys` 输入成功
- 拦截到的AJAX请求：
  ```
  POST /ajax/comments/reply
  id=5220670540612942&cid=5284131541882805&comment=footer回复测试9578
  ```
- 注意：`cid=5284131541882805` 不等于inbox URL中的任何参数，证实前端有独立的评论ID来源

### 7.2 API方式回复测试（失败案例）

- `buildComments fetch_level=1` 对根评论 `5284025771492373` 返回0条子评论
- 用 `cid=root_comment_id, reply_id=root_comment_id` 发送回复 → 回复挂到根评论下面（位置错误）
- 添加"回复@xxx:"文本前缀 → 视觉上有引用，但回复位置仍然在根评论下（不是楼中楼）

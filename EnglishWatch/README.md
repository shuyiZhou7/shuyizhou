# EnglishWatch：Apple Watch 背单词

独立运行的 watchOS App（不需要 iPhone 上装配套 App），SwiftUI 编写，支持 watchOS 10 及以上。

## 功能

- **单词卡片**：英文 + 音标，自动朗读；点「显示释义」看中文和例句，点例句可朗读
- **间隔重复**：选「忘了 / 记得 / 简单」，按莱特纳盒子法安排复习（当天 → 1 → 2 → 4 → 7 → 15 → 30 → 60 天）；
  「忘了」的单词本轮最后会再出现一次
- **小测验**：看英文选中文，四选一，答错的已学单词会放回复习队列
- **统计与设置**：连续学习天数、今日新学/复习、已学/已掌握数量；每日新词数量（5~30）、自动发音开关
- 震动反馈；学习进度保存在手表本地
- 内置 100 个常用词（`Resources/Words.json`），可以按同样格式自行添加

## 文件

```
Sources/
  EnglishWatchApp.swift  # 入口
  Word.swift             # 单词模型，读取 Words.json
  StudyStore.swift       # 学习进度、间隔重复算法、测验出题、本地保存
  Speaker.swift          # 英文朗读、震动
  ContentView.swift      # 首页
  StudyView.swift        # 单词卡片
  QuizView.swift         # 小测验
  StatsView.swift        # 统计与设置
Resources/
  Words.json             # 词库
```

## 安装到手表

需要：一台 Mac（装好 App Store 里免费的 **Xcode 16 或更新版本**）、一个 Apple ID、和手表配对的 iPhone。

1. 打开 Xcode → **File → New → Project** → 选 **watchOS → App** → Next。
   - Product Name 填 `EnglishWatch`
   - Interface 选 **SwiftUI**，并选 **Watch-only App**
2. 在左侧文件列表里，找到 `EnglishWatch Watch App` 文件夹，**删掉** Xcode 自动生成的
   `ContentView.swift` 和 `EnglishWatchApp.swift`（选 Move to Trash）。
3. 把本目录 `Sources/` 里的 8 个 `.swift` 文件和 `Resources/Words.json` 拖进这个文件夹，
   弹窗里勾选 **Copy items if needed**，并确认勾选了 Watch App 这个 target。
4. 点项目名 → **Signing & Capabilities** → Team 选你的 Apple ID（Personal Team）。
5. iPhone 用数据线连接 Mac，手表保持和 iPhone 配对、解锁。
   第一次需要在 iPhone 和手表上分别打开 **设置 → 隐私与安全性 → 开发者模式**，按提示重启。
6. Xcode 顶部的运行目标选你的 Apple Watch，点 ▶ 运行。第一次安装可能要等几分钟。

> 用免费 Apple ID 安装的 App 有效期 7 天，过期后用 Xcode 重新运行一次即可。
> 加入 Apple 开发者计划（每年 99 美元）可以延长到 1 年，也能用 TestFlight 安装。

## 添加单词

按这个格式往 `Words.json` 里加条目，`word` 和 `meaning` 不要重复：

```json
{"word": "example", "phonetic": "/ɪɡˈzæmpl/", "meaning": "n. 例子",
 "example": "Can you give me an example?", "exampleZh": "你能举个例子吗？"}
```

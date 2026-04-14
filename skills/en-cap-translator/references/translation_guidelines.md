# Translation Guidelines

Use this reference while translating. Keep `SKILL.md` as the execution guide and keep detailed terminology here.

## Canonical Output Contract

The packaging scripts expect canonical bilingual markdown:

- One English heading, paragraph, or list item immediately followed by its Chinese translation.
- The first bilingual paragraph must be a document summary for the whole deliverable.
- The same heading prefix, clause number, or list marker on both lines.
- Blank lines between paragraph groups are allowed and recommended.
- Markdown tables stay single-language and appear once.
- Markdown images, figure captions, annex labels, formulas, and code blocks stay single-language unless the user explicitly asks otherwise.
- Tables and images stay in their original relative positions.

## Style Rules

- Translate legal and technical meaning, not tone.
- Write the first paragraph as a concise document summary before the main body.
- Preserve all requirement verbs such as `shall`, `must`, `may`, and `should` with equivalent force.
- Keep references, part numbers, annex labels, and test IDs exact.
- Keep units and numeric values unchanged.
- Keep glossary choices consistent within one deliverable.
- For polished Chinese wording, read [chinese-regulatory-style.md](chinese-regulatory-style.md) and follow its preferred sentence patterns.

## Chinese Regulatory Style

- Prefer regulatory Chinese over literal translation.
- Use `可计分`, not `具有得分资格` or `可获得该项评分`.
- Use `失效`, not `不具功能`.
- Use `视为` / `认定为` according to whether the source defines a state or classifies a state.
- Use `充分说明` / `充分证据`, not `有力信息`.
- For official programme names, keep the English name on first mention and add Chinese only when it improves readability.

## Headings

- Preserve numbering exactly.
- Translate the heading text only.

Example:

```text
5.2 Test Conditions
5.2 测试条件
```

## Lists

- Preserve the marker on both lines.
- Translate each list item independently.

Example:

```text
- The warning shall remain visible.
- 警告应保持可见。
```

## Tables And Figures

- Keep markdown tables unchanged.
- Keep markdown images unchanged and at their original positions.
- Keep `Figure`, `Table`, `Annex`, and similar captions unchanged by default.
- Add a Chinese note only when the user explicitly asks for bilingual captions.

## References And Cross-References

- Keep clause numbers exact.
- Keep inline references readable.

Examples:

- `see clause 4.2` -> `see clause 4.2 (见第 4.2 条)`
- `refer to Table 7` -> `refer to Table 7 (见表 7)`

## Abbreviations

- Expand on first appearance only when the source does so or when the user asks for an explanatory translation.
- Keep the English acronym in the Chinese line when it is the operational term used by engineers.

Example:

```text
Operational Design Domain (ODD)
设计运行域（ODD）
```

## Controlled Glossary

Prefer these translations unless a user-provided glossary overrides them.

| English | Preferred Chinese | Notes |
| --- | --- | --- |
| Operational Design Domain | 设计运行域 | ODD |
| Dynamic Driving Task | 动态驾驶任务 | DDT |
| Minimal Risk Condition | 最小风险状态 | MRC |
| Automated Lane Keeping System | 自动车道保持系统 | ALKS |
| Advanced Driver Assistance Systems | 高级驾驶辅助系统 | ADAS |
| Autonomous Emergency Braking | 自动紧急制动 | AEB |
| Lane Support Systems | 车道辅助系统 | LSS |
| Vulnerable Road Users | 弱势道路使用者 | VRU |
| Steering Equipment | 转向装置 | UN R79 context |
| Corrective Steering Function | 修正转向功能 | CSF |
| Emergency Steering Function | 紧急转向功能 | ESF |
| Automatically Commanded Steering Function | 自动指令转向功能 | ACSF; keep acronym if the Chinese rendering is disputed |
| Time To Collision | 碰撞时间 | TTC |

## Quality Checklist

Use this checklist before validation:

- Every English translatable block has a Chinese partner directly below it.
- The first bilingual paragraph is a document summary.
- Every heading number and list marker is unchanged.
- No table cells were translated by accident.
- Tables and images remain in place.
- No `TODO_TRANSLATE` or `[ZH: ...]` placeholders remain.
- Modal verbs and safety constraints preserve the original force.
- Terms remain consistent within the same regulation family.

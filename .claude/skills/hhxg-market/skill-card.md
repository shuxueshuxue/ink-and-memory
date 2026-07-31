## Description: <br>
A 股量化数据助手 — 日报快照、A股日历、融资融券、实时快讯，零配置无需安装任何依赖。 <br>

This skill is ready for commercial/non-commercial use. <br>

## Publisher: <br>
[Niceck](https://clawhub.ai/user/Niceck) <br>

### License/Terms of Use: <br>
MIT <br>


## Use Case: <br>
External users and developers use this skill to retrieve public A-share market snapshots, trading calendars, margin data, and financial news inside an agent workflow or from terminal scripts. <br>

### Deployment Geography for Use: <br>
Global <br>

## Known Risks and Mitigations: <br>
Risk: The skill contacts hhxg.top for public market data and may show hhxg.top promotional or tool links. <br>
Mitigation: Install and use it only when that network dependency and those links are acceptable for the target environment. <br>
Risk: Market data may be served from local cached JSON when the network is unavailable. <br>
Mitigation: Check the skill's date and cache notices before relying on recency-sensitive output. <br>
Risk: The README install command includes rm -rf against a skill directory path. <br>
Mitigation: Inspect the command before running it and confirm the removal path points only to the intended hhxg-market skill directory. <br>
Risk: A-share market summaries can be mistaken for investment advice. <br>
Mitigation: Treat the output as research reference material and review source data before making financial decisions. <br>


## Reference(s): <br>
- [ClawHub skill page](https://clawhub.ai/Niceck/hhxg-market) <br>
- [ClawHub publisher profile](https://clawhub.ai/user/Niceck) <br>
- [Data schema reference](references/data-schema.md) <br>
- [恢恢量化](https://hhxg.top) <br>
- [hhxg.top public data endpoint](https://hhxg.top/static/data/) <br>


## Skill Output: <br>
**Output Type(s):** [Text, Markdown, JSON, Shell commands, Guidance] <br>
**Output Format:** [Markdown reports and optional JSON data emitted by Python scripts, with shell commands for invocation.] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Fetches public hhxg.top data, retries once on network errors, and can fall back to locally cached JSON.] <br>

## Skill Version(s): <br>
1.1.0 (source: server-resolved release metadata) <br>

## Ethical Considerations: <br>
Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment. <br>

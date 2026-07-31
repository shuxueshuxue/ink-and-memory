## Description: <br>
获取高质量 A 股投资数据，基于 investment_data 项目，支持日终价格、涨跌停数据、指数数据等查询。 <br>

This skill is ready for commercial/non-commercial use. <br>

## Publisher: <br>
[StanleyChanH](https://clawhub.ai/user/StanleyChanH) <br>

### License/Terms of Use: <br>
Apache 2.0 <br>


## Use Case: <br>
Developers and quantitative research users can use this skill to query, export, and script access to A-share price, limit-up/limit-down, stock list, and index-related data. Returned market data should be treated as untrusted until the placeholder data-loading behavior is replaced and validated. <br>

### Deployment Geography for Use: <br>
Global <br>

## Known Risks and Mitigations: <br>
Risk: Core data APIs may return placeholder or fake market data while presenting the output as investment data. <br>
Mitigation: Do not use returned prices, limits, stock lists, or index data for trading, backtesting, reporting, or automated decisions until real data-loading code is implemented and independently validated. <br>
Risk: The downloader extracts a remote archive without verification. <br>
Mitigation: Run downloads in a controlled directory and verify or harden archive handling before use. <br>


## Reference(s): <br>
- [ClawHub skill page](https://clawhub.ai/StanleyChanH/investment-data) <br>
- [Publisher profile](https://clawhub.ai/user/StanleyChanH) <br>
- [Field reference](references/fields.md) <br>
- [Usage examples](examples/usage_examples.md) <br>
- [investment_data project](https://github.com/chenditc/investment_data) <br>
- [DoltHub investment_data repository](https://www.dolthub.com/repositories/chenditc/investment_data) <br>


## Skill Output: <br>
**Output Type(s):** [text, markdown, code, shell commands, configuration, guidance] <br>
**Output Format:** [Markdown guidance with Python and shell command examples; scripts may emit tabular text, CSV, JSON, Excel, or exported files.] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Requires python3, wget, tar, and Python dependencies including pandas, numpy, requests, pyyaml, and openpyxl.] <br>

## Skill Version(s): <br>
1.0.0 (source: server-resolved release metadata) <br>

## Ethical Considerations: <br>
Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment. <br>

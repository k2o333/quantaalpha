"""
更新报告生成器
收集更新过程中的统计信息并生成结构化报告
"""
import json
import logging
import os
from datetime import datetime
from typing import List, Optional

from .models import (
    ReportFormat, 
    InterfaceUpdateResult, 
    UpdateResult,
    UpdateSummary,
    UpdateStatus
)

logger = logging.getLogger(__name__)


class UpdateReporter:
    """更新报告器 - 生成更新报告"""
    
    def __init__(self):
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.interface_results: List[InterfaceUpdateResult] = []
    
    def record_update_start(self):
        """记录更新开始"""
        self.start_time = datetime.now()
        logger.info(f"更新开始: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def record_update_end(self):
        """记录更新结束"""
        self.end_time = datetime.now()
        logger.info(f"更新结束: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def record_interface_start(self, interface_name: str):
        """记录接口更新开始"""
        logger.info(f"开始更新接口: {interface_name}")
    
    def record_interface_result(self, result: InterfaceUpdateResult):
        """记录接口更新结果"""
        self.interface_results.append(result)
        
        status_emoji = {
            UpdateStatus.SUCCESS: "✓",
            UpdateStatus.FAILED: "✗",
            UpdateStatus.SKIPPED: "○"
        }.get(result.status, "?")
        
        msg = f"{status_emoji} {result.interface_name}: {result.status.name}"
        if result.record_count > 0:
            msg += f" ({result.record_count} 条记录)"
        if result.duration_seconds > 0:
            msg += f" [{result.duration_seconds:.2f}s]"
        if result.skip_reason:
            msg += f" - {result.skip_reason}"
        if result.error_message:
            msg += f" - 错误: {result.error_message}"
        
        if result.status == UpdateStatus.FAILED:
            logger.error(msg)
        elif result.status == UpdateStatus.SKIPPED:
            logger.info(msg)
        else:
            logger.info(msg)
    
    def generate_report(
        self, 
        format: ReportFormat = ReportFormat.MARKDOWN
    ) -> str:
        """
        生成更新报告
        
        Args:
            format: 报告格式
            
        Returns:
            str: 报告内容
        """
        if format == ReportFormat.MARKDOWN:
            return self._generate_markdown_report()
        elif format == ReportFormat.JSON:
            return self._generate_json_report()
        elif format == ReportFormat.HTML:
            return self._generate_html_report()
        else:
            raise ValueError(f"不支持的报告格式: {format}")
    
    def _generate_markdown_report(self) -> str:
        """生成 Markdown 格式报告"""
        lines = []
        
        # 标题
        lines.append("# App4 增量更新报告\n")
        
        # 概览
        lines.append("## 概览\n")
        lines.append(f"- **开始时间**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else 'N/A'}")
        lines.append(f"- **结束时间**: {self.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.end_time else 'N/A'}")
        
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
            lines.append(f"- **总耗时**: {self._format_duration(duration)}")
        
        # 统计
        summary = self.get_summary()
        lines.append(f"- **总接口数**: {summary.total}")
        lines.append(f"- **成功**: {summary.success}")
        lines.append(f"- **跳过**: {summary.skipped}")
        lines.append(f"- **失败**: {summary.failed}")
        lines.append(f"- **成功率**: {summary.success_rate * 100:.1f}%")
        lines.append(f"- **总记录数**: {summary.total_records}\n")
        
        # 接口详情
        lines.append("## 接口详情\n")
        lines.append("| 接口名称 | 状态 | 日期范围 | 记录数 | 耗时 | 备注 |")
        lines.append("|---------|------|---------|--------|------|------|")
        
        for result in self.interface_results:
            status_icon = {
                UpdateStatus.SUCCESS: "✓ 成功",
                UpdateStatus.FAILED: "✗ 失败",
                UpdateStatus.SKIPPED: "○ 跳过"
            }.get(result.status, "?")
            
            date_range = str(result.date_range) if result.date_range else "-"
            record_count = str(result.record_count) if result.record_count > 0 else "-"
            duration = f"{result.duration_seconds:.2f}s" if result.duration_seconds > 0 else "-"
            
            note = ""
            if result.skip_reason:
                note = result.skip_reason
            elif result.error_message:
                note = f"错误: {result.error_message[:50]}"
            
            lines.append(
                f"| {result.interface_name} | {status_icon} | {date_range} | "
                f"{record_count} | {duration} | {note} |"
            )
        
        lines.append("")
        
        # 失败汇总
        failed_results = [r for r in self.interface_results if r.status == UpdateStatus.FAILED]
        if failed_results:
            lines.append("## 失败汇总\n")
            for result in failed_results:
                lines.append(f"### {result.interface_name}")
                lines.append(f"- 错误: {result.error_message}")
                if result.date_range:
                    lines.append(f"- 日期范围: {result.date_range}")
                lines.append("")
        
        return "\n".join(lines)
    
    def _generate_json_report(self) -> str:
        """生成 JSON 格式报告"""
        summary = self.get_summary()
        
        report_data = {
            "metadata": {
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "duration_seconds": summary.duration_seconds
            },
            "summary": {
                "total": summary.total,
                "success": summary.success,
                "failed": summary.failed,
                "skipped": summary.skipped,
                "success_rate": summary.success_rate,
                "total_records": summary.total_records
            },
            "interfaces": []
        }
        
        for result in self.interface_results:
            report_data["interfaces"].append({
                "name": result.interface_name,
                "status": result.status.name,
                "date_range": {
                    "start": result.date_range.start_date if result.date_range else None,
                    "end": result.date_range.end_date if result.date_range else None
                },
                "record_count": result.record_count,
                "duration_seconds": result.duration_seconds,
                "error_message": result.error_message,
                "skip_reason": result.skip_reason
            })
        
        return json.dumps(report_data, indent=2, ensure_ascii=False)
    
    def _generate_html_report(self) -> str:
        """生成 HTML 格式报告"""
        summary = self.get_summary()
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>App4 增量更新报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .summary-item {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; border-left: 4px solid #4CAF50; }}
        .summary-item.failed {{ border-left-color: #f44336; }}
        .summary-item.skipped {{ border-left-color: #ff9800; }}
        .summary-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
        .summary-value {{ font-size: 24px; font-weight: bold; color: #333; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .status-success {{ color: #4CAF50; font-weight: bold; }}
        .status-failed {{ color: #f44336; font-weight: bold; }}
        .status-skipped {{ color: #ff9800; font-weight: bold; }}
        .error-section {{ background-color: #ffebee; padding: 15px; border-radius: 5px; margin-top: 20px; }}
        .timestamp {{ color: #666; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>App4 增量更新报告</h1>
        <p class="timestamp">
            开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else 'N/A'} | 
            结束时间: {self.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.end_time else 'N/A'} | 
            耗时: {self._format_duration(summary.duration_seconds)}
        </p>
        
        <h2>概览</h2>
        <div class="summary">
            <div class="summary-item">
                <div class="summary-label">总接口数</div>
                <div class="summary-value">{summary.total}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">成功</div>
                <div class="summary-value" style="color: #4CAF50;">{summary.success}</div>
            </div>
            <div class="summary-item skipped">
                <div class="summary-label">跳过</div>
                <div class="summary-value" style="color: #ff9800;">{summary.skipped}</div>
            </div>
            <div class="summary-item failed">
                <div class="summary-label">失败</div>
                <div class="summary-value" style="color: #f44336;">{summary.failed}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">成功率</div>
                <div class="summary-value">{summary.success_rate * 100:.1f}%</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">总记录数</div>
                <div class="summary-value">{summary.total_records:,}</div>
            </div>
        </div>
        
        <h2>接口详情</h2>
        <table>
            <thead>
                <tr>
                    <th>接口名称</th>
                    <th>状态</th>
                    <th>日期范围</th>
                    <th>记录数</th>
                    <th>耗时</th>
                    <th>备注</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for result in self.interface_results:
            status_class = {
                UpdateStatus.SUCCESS: "status-success",
                UpdateStatus.FAILED: "status-failed",
                UpdateStatus.SKIPPED: "status-skipped"
            }.get(result.status, "")
            
            status_text = {
                UpdateStatus.SUCCESS: "成功",
                UpdateStatus.FAILED: "失败",
                UpdateStatus.SKIPPED: "跳过"
            }.get(result.status, "未知")
            
            date_range = str(result.date_range) if result.date_range else "-"
            record_count = result.record_count if result.record_count > 0 else "-"
            duration = f"{result.duration_seconds:.2f}s" if result.duration_seconds > 0 else "-"
            
            note = ""
            if result.skip_reason:
                note = result.skip_reason
            elif result.error_message:
                note = f"错误: {result.error_message[:100]}"
            
            html += f"""
                <tr>
                    <td>{result.interface_name}</td>
                    <td class="{status_class}">{status_text}</td>
                    <td>{date_range}</td>
                    <td>{record_count}</td>
                    <td>{duration}</td>
                    <td>{note}</td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
"""
        
        # 失败详情
        failed_results = [r for r in self.interface_results if r.status == UpdateStatus.FAILED]
        if failed_results:
            html += """
        <h2>失败详情</h2>
        <div class="error-section">
"""
            for result in failed_results:
                html += f"""
            <h3>{result.interface_name}</h3>
            <p><strong>错误:</strong> {result.error_message}</p>
"""
            html += """
        </div>
"""
        
        html += """
    </div>
</body>
</html>
"""
        
        return html
    
    def get_summary(self) -> UpdateSummary:
        """获取更新摘要"""
        total = len(self.interface_results)
        success = sum(1 for r in self.interface_results if r.status == UpdateStatus.SUCCESS)
        failed = sum(1 for r in self.interface_results if r.status == UpdateStatus.FAILED)
        skipped = sum(1 for r in self.interface_results if r.status == UpdateStatus.SKIPPED)
        total_records = sum(r.record_count for r in self.interface_results)
        
        duration = 0.0
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
        
        return UpdateSummary(
            total=total,
            success=success,
            failed=failed,
            skipped=skipped,
            total_records=total_records,
            duration_seconds=duration
        )
    
    def save_report(
        self, 
        filepath: str, 
        format: ReportFormat = ReportFormat.MARKDOWN
    ):
        """
        保存报告到文件
        
        Args:
            filepath: 文件路径
            format: 报告格式
        """
        report_content = self.generate_report(format)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"报告已保存到: {filepath}")
    
    def _format_duration(self, seconds: float) -> str:
        """格式化持续时间"""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.2f}小时"
    
    def reset(self):
        """重置报告器状态"""
        self.start_time = None
        self.end_time = None
        self.interface_results = []

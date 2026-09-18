import type { ReactNode } from 'react';
import { Typography, Tag, Empty, List } from 'antd';
import type { Report, Evidence, Ioc } from '../../types/models';

function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <Typography.Text strong style={{ display: 'block', margin: '12px 0 4px', fontSize: 12 }}>
      {children}
    </Typography.Text>
  );
}

export default function ReportView({ report }: { report: Report | null }) {
  if (!report) return <Empty description="暂无结构化调查报告" />;
  const evidence = report.evidence ?? [];
  const attackChain = report.attack_chain ?? [];
  const iocs = report.iocs ?? [];
  const unknowns = report.unknowns ?? [];
  const remediations = report.remediations ?? [];

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Typography.Text strong style={{ fontSize: 15 }}>{report.verdict}</Typography.Text>
        <Typography.Text type="secondary"> · 置信度 {report.confidence}</Typography.Text>
      </div>
      {report.digest && <Typography.Paragraph style={{ marginBottom: 8 }}>{report.digest}</Typography.Paragraph>}

      {evidence.length > 0 && (
        <>
          <SectionTitle>证据</SectionTitle>
          <List<Evidence>
            size="small"
            dataSource={evidence}
            renderItem={(e) => (
              <List.Item>
                <Typography.Text>
                  <Typography.Text strong>{e.fact}</Typography.Text> → {e.conclusion}
                </Typography.Text>
              </List.Item>
            )}
          />
        </>
      )}

      {attackChain.length > 0 && (
        <>
          <SectionTitle>攻击链</SectionTitle>
          <List<{ phase: string; description: string }>
            size="small"
            dataSource={attackChain}
            renderItem={(a) => (
              <List.Item>
                <Typography.Text>
                  <Typography.Text strong>{a.phase}</Typography.Text>：{a.description}
                </Typography.Text>
              </List.Item>
            )}
          />
        </>
      )}

      {iocs.length > 0 && (
        <>
          <SectionTitle>IOC</SectionTitle>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {iocs.map((ioc: Ioc, i: number) => (
              <Tag key={i} title={ioc.context}>{ioc.value}</Tag>
            ))}
          </div>
        </>
      )}

      {unknowns.length > 0 && (
        <>
          <SectionTitle>待查</SectionTitle>
          <List<string> size="small" dataSource={unknowns} renderItem={(u) => <List.Item>{u}</List.Item>} />
        </>
      )}

      {remediations.length > 0 && (
        <>
          <SectionTitle>处置建议</SectionTitle>
          <List<string> size="small" dataSource={remediations} renderItem={(r) => <List.Item>{r}</List.Item>} />
        </>
      )}
    </div>
  );
}

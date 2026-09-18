import type { ReactNode } from 'react';
import { Typography, Tag, Empty, Listy } from 'antd';
import type { Report, Evidence, Ioc } from '../../types/models';

function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <Typography.Text strong style={{ display: 'block', margin: '12px 0 4px', fontSize: 12 }}>
      {children}
    </Typography.Text>
  );
}

const itemStyle: React.CSSProperties = { padding: '4px 0', fontSize: 13 };

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
          <Listy<Evidence>
            items={evidence}
            rowKey={(e) => e.fact}
            itemRender={(e) => (
              <div style={itemStyle}>
                <Typography.Text>
                  <Typography.Text strong>{e.fact}</Typography.Text> → {e.conclusion}
                </Typography.Text>
              </div>
            )}
          />
        </>
      )}

      {attackChain.length > 0 && (
        <>
          <SectionTitle>攻击链</SectionTitle>
          <Listy<{ phase: string; description: string }>
            items={attackChain}
            rowKey={(a) => a.phase}
            itemRender={(a) => (
              <div style={itemStyle}>
                <Typography.Text>
                  <Typography.Text strong>{a.phase}</Typography.Text>：{a.description}
                </Typography.Text>
              </div>
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
          <Listy<string>
            items={unknowns}
            rowKey={(u) => u}
            itemRender={(u) => <div style={itemStyle}>{u}</div>}
          />
        </>
      )}

      {remediations.length > 0 && (
        <>
          <SectionTitle>处置建议</SectionTitle>
          <Listy<string>
            items={remediations}
            rowKey={(r) => r}
            itemRender={(r) => <div style={itemStyle}>{r}</div>}
          />
        </>
      )}
    </div>
  );
}

import React from 'react';
import { ResponsivePie } from '@nivo/pie';

type SemicircleGaugeProps = {
  value?: number;
  max?: number;
};

function SemicircleGauge({ value = 0, max = 100 }: SemicircleGaugeProps) {
  const safeMax = max > 0 ? max : 1;
  const clampedValue = Math.min(Math.max(value, 0), safeMax);
  const remainder = safeMax - clampedValue;

  const data = [
    { id: 'filled', value: clampedValue, color: '#3B4A6B' },
    { id: 'empty', value: remainder, color: '#ECEDF1' },
  ];

  return (
    <div style={{ position: 'relative', width: '200px', height: '200px' }}>
      <ResponsivePie
        data={data}
        startAngle={-135}
        endAngle={135}
        sortByValue={false}
        colors={(datum) => datum.data.color as string}
        innerRadius={0.85}
        cornerRadius={45}
        activeOuterRadiusOffset={0}
        enableArcLinkLabels={false}
        enableArcLabels={false}
        padAngle={0}
      />
      <span
        style={{
          position: 'absolute',
          top: '55%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          color: '#3B4A6B',
          fontWeight: 600,
          fontSize: 36,
        }}
      >
        {value}%
      </span>
    </div>
  );
};

export default SemicircleGauge;

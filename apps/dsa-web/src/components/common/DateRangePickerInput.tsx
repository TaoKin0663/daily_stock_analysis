import React, { useCallback, useMemo } from 'react';
import { parseDate } from '@internationalized/date';
import type { DateValue } from 'react-aria-components';
import type { RangeValue } from 'react-aria-components';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { DateField, DateRangePicker, RangeCalendar } from '@heroui/react';

function toDateValue(raw: string): DateValue | null {
  if (!raw) return null;
  try {
    return parseDate(raw);
  } catch {
    return null;
  }
}

export interface DateRangePickerInputProps {
  startValue: string;
  endValue: string;
  onStartChange: (value: string) => void;
  onEndChange: (value: string) => void;
  disabled?: boolean;
  'aria-label'?: string;
}

export const DateRangePickerInput: React.FC<DateRangePickerInputProps> = ({
  startValue,
  endValue,
  onStartChange,
  onEndChange,
  disabled,
  'aria-label': ariaLabel,
}) => {
  const value = useMemo((): RangeValue<DateValue> | null => {
    const start = toDateValue(startValue);
    const end = toDateValue(endValue);
    return start && end ? { start, end } : null;
  }, [startValue, endValue]);

  const handleChange = useCallback(
    (range: RangeValue<DateValue> | null) => {
      onStartChange(range?.start?.toString() ?? '');
      onEndChange(range?.end?.toString() ?? '');
    },
    [onStartChange, onEndChange],
  );

  return (
    <DateRangePicker
      value={value as any}
      onChange={handleChange as any}
      isDisabled={disabled}
      aria-label={ariaLabel}
      className="w-full"
    >
      <DateField.Group fullWidth>
        <DateField.Input slot="start">
          {(segment) => <DateField.Segment segment={segment} />}
        </DateField.Input>
        <DateRangePicker.RangeSeparator />
        <DateField.Input slot="end">
          {(segment) => <DateField.Segment segment={segment} />}
        </DateField.Input>
        <DateField.Suffix>
          <DateRangePicker.Trigger>
            <DateRangePicker.TriggerIndicator />
          </DateRangePicker.Trigger>
        </DateField.Suffix>
      </DateField.Group>
      <DateRangePicker.Popover>
        <RangeCalendar aria-label={ariaLabel ?? 'Date range'}>
          <RangeCalendar.Header>
            <RangeCalendar.YearPickerTrigger>
              <RangeCalendar.YearPickerTriggerHeading />
              <RangeCalendar.YearPickerTriggerIndicator />
            </RangeCalendar.YearPickerTrigger>
            <RangeCalendar.NavButton slot="previous">
              <ChevronLeft className="h-4 w-4" />
            </RangeCalendar.NavButton>
            <RangeCalendar.NavButton slot="next">
              <ChevronRight className="h-4 w-4" />
            </RangeCalendar.NavButton>
          </RangeCalendar.Header>
          <RangeCalendar.Grid>
            <RangeCalendar.GridHeader>
              {(day) => <RangeCalendar.HeaderCell>{day}</RangeCalendar.HeaderCell>}
            </RangeCalendar.GridHeader>
            <RangeCalendar.GridBody>
              {(date) => <RangeCalendar.Cell date={date} />}
            </RangeCalendar.GridBody>
          </RangeCalendar.Grid>
          <RangeCalendar.YearPickerGrid>
            <RangeCalendar.YearPickerGridBody>
              {({ year }) => <RangeCalendar.YearPickerCell year={year} />}
            </RangeCalendar.YearPickerGridBody>
          </RangeCalendar.YearPickerGrid>
        </RangeCalendar>
      </DateRangePicker.Popover>
    </DateRangePicker>
  );
};

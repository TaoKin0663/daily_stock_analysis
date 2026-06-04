import { useState } from 'react';
import type React from 'react';
import { Badge, Button, Input, ListBox, Select, Switch, TextArea, TimeField } from '@heroui/react';
import { Time } from '@internationalized/date';
import type { ConfigValidationIssue, SystemConfigFieldSchema, SystemConfigItem } from '../../types/systemConfig';
import { getFieldDescriptionZh, getFieldTitleZh } from '../../utils/systemConfigI18n';
import { cn } from '../../utils/cn';
import { EyeToggleIcon } from '../common';

function normalizeSelectOptions(options: SystemConfigFieldSchema['options'] = []) {
  return options.map((option) => {
    if (typeof option === 'string') {
      return { value: option, label: option };
    }

    return option;
  });
}

function isMultiValueField(item: SystemConfigItem): boolean {
  const validation = (item.schema?.validation ?? {}) as Record<string, unknown>;
  return Boolean(validation.multiValue ?? validation.multi_value);
}

function parseMultiValues(value: string): string[] {
  if (!value) {
    return [''];
  }

  const values = value.split(',').map((entry) => entry.trim());
  return values.length ? values : [''];
}

function serializeMultiValues(values: string[]): string {
  return values.map((entry) => entry.trim()).join(',');
}

interface SettingsFieldProps {
  item: SystemConfigItem;
  value: string;
  disabled?: boolean;
  onChange: (key: string, value: string) => void;
  issues?: ConfigValidationIssue[];
}

interface PasswordVisibilityButtonProps {
  visible: boolean;
  disabled: boolean;
  onToggle: () => void;
}

const PasswordVisibilityButton: React.FC<PasswordVisibilityButtonProps> = ({
  visible,
  disabled,
  onToggle,
}) => (
  <button
    type="button"
    className={cn(
      'absolute right-2 top-1/2 z-10 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg border transition-all duration-200 focus:outline-none focus:ring-2',
      visible
        ? 'border-warning/40 bg-warning/15 text-warning shadow-[0_0_10px_hsla(var(--warning),0.15)]'
        : 'border-border/40 bg-muted/20 text-muted-text hover:border-warning/40 hover:text-warning hover:shadow-[0_0_10px_hsla(var(--warning),0.15)] focus:ring-primary/30',
      disabled ? 'cursor-not-allowed opacity-50' : '',
    )}
    onClick={onToggle}
    disabled={disabled}
    tabIndex={-1}
  >
    <EyeToggleIcon visible={visible} />
  </button>
);

function renderFieldControl(
  item: SystemConfigItem,
  value: string,
  disabled: boolean,
  onChange: (nextValue: string) => void,
  isPasswordEditable: boolean,
  onPasswordFocus: () => void,
  controlId: string,
  visiblePasswordInputIds: Set<string>,
  onTogglePasswordVisibility: (inputId: string) => void,
) {
  const schema = item.schema;
  const controlType = schema?.uiControl ?? 'text';
  const isMultiValue = isMultiValueField(item);

  if (controlType === 'switch') {
    const checked = value.trim().toLowerCase() === 'true';

    return (
      <Switch
        id={controlId}
        isSelected={checked}
        isDisabled={disabled || !schema?.isEditable}
        onChange={(isSelected) => onChange(isSelected ? 'true' : 'false')}
        className="text-sm text-secondary-text"
        style={{
          '--switch-control-bg': 'var(--settings-secondary-bg)',
          '--switch-control-bg-hover': 'var(--settings-secondary-bg-hover)',
          '--switch-control-bg-pressed': 'var(--settings-secondary-bg-hover)',
          '--switch-control-bg-checked': 'hsl(var(--primary))',
          '--switch-control-bg-checked-hover': 'hsl(var(--primary) / 0.86)',
        } as React.CSSProperties}
      >
        <Switch.Control className="ring-1 ring-[var(--settings-border-soft)] transition-shadow data-[disabled=true]:opacity-60">
          <Switch.Thumb />
        </Switch.Control>
      </Switch>
    );
  }

  if (controlType === 'textarea') {
    return (
      <TextArea
        id={controlId}
        className="min-h-[92px] resize-y"
        fullWidth
        value={value}
        disabled={disabled || !schema?.isEditable}
        onChange={(event) => onChange(event.target.value)}
      />
    );
  }

  if (controlType === 'select' && schema?.options?.length) {
    const options = normalizeSelectOptions(schema.options);

    return (
      <Select
        id={controlId}
        selectedKey={value || null}
        onSelectionChange={(key) => onChange(key === null ? '' : String(key))}
        isDisabled={disabled || !schema.isEditable}
        placeholder="请选择"
        fullWidth
      >
        <Select.Trigger id={controlId}>
          <Select.Value />
          <Select.Indicator />
        </Select.Trigger>
        <Select.Popover>
          <ListBox>
            {options.map((option) => (
              <ListBox.Item key={option.value} id={option.value} textValue={option.label}>
                {option.label}
                <ListBox.ItemIndicator />
              </ListBox.Item>
            ))}
          </ListBox>
        </Select.Popover>
      </Select>
    );
  }

  if (controlType === 'password') {
    if (isMultiValue) {
      const values = parseMultiValues(value);

      return (
        <div className="space-y-2">
          {values.map((entry, index) => (
            <div className="flex items-center gap-2" key={`${item.key}-${index}`}>
              <div className="relative flex-1">
                {(() => {
                  const passwordInputId = index === 0 ? controlId : `${controlId}-${index}`;
                  const isPasswordVisible = visiblePasswordInputIds.has(passwordInputId);

                  return (
                    <>
                      <Input
                        type={isPasswordVisible ? 'text' : 'password'}
                        id={passwordInputId}
                        className="pr-12"
                        fullWidth
                        readOnly={!isPasswordEditable}
                        onFocus={onPasswordFocus}
                        value={entry}
                        disabled={disabled || !schema?.isEditable}
                        onChange={(event) => {
                          const nextValues = [...values];
                          nextValues[index] = event.target.value;
                          onChange(serializeMultiValues(nextValues));
                        }}
                      />
                      <PasswordVisibilityButton
                        visible={isPasswordVisible}
                        disabled={disabled || !schema?.isEditable}
                        onToggle={() => onTogglePasswordVisibility(passwordInputId)}
                      />
                    </>
                  );
                })()}
              </div>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="px-3 text-xs text-muted-text shadow-none hover:text-danger"
                isDisabled={disabled || !schema?.isEditable || values.length <= 1}
                onPress={() => {
                  const nextValues = values.filter((_, rowIndex) => rowIndex !== index);
                  onChange(serializeMultiValues(nextValues.length ? nextValues : ['']));
                }}
              >
                删除
              </Button>
            </div>
          ))}

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="text-xs shadow-none"
              isDisabled={disabled || !schema?.isEditable}
              onPress={() => onChange(serializeMultiValues([...values, '']))}
            >
              添加 Key
            </Button>
          </div>
        </div>
      );
    }

    const isPasswordVisible = visiblePasswordInputIds.has(controlId);

    return (
      <div className="relative">
        <Input
          type={isPasswordVisible ? 'text' : 'password'}
          id={controlId}
          className="pr-12"
          fullWidth
          readOnly={!isPasswordEditable}
          onFocus={onPasswordFocus}
          value={value}
          disabled={disabled || !schema?.isEditable}
          onChange={(event) => onChange(event.target.value)}
        />
        <PasswordVisibilityButton
          visible={isPasswordVisible}
          disabled={disabled || !schema?.isEditable}
          onToggle={() => onTogglePasswordVisibility(controlId)}
        />
      </div>
    );
  }

  if (controlType === 'time') {
    // 解析 HH:mm 字符串 → Time 对象，分钟取整到最近 5 分钟
    let timeValue: Time | null = null;
    if (value) {
      const match = /^(\d{1,2}):(\d{2})$/.exec(value.trim());
      if (match) {
        const rawHour = Number(match[1]);
        const rawMinute = Number(match[2]);
        const rounded = Math.round(rawMinute / 5) * 5;
        if (rounded === 60) {
          timeValue = new Time((rawHour + 1) % 24, 0);
        } else {
          timeValue = new Time(rawHour, rounded);
        }
      }
    }

    return (
      <TimeField
        id={controlId}
        value={timeValue}
        isDisabled={disabled || !schema?.isEditable}
        granularity="minute"
        hourCycle={24}
        className="w-full"
        onChange={(newTime) => {
          if (!newTime) {
            onChange('');
            return;
          }
          // 分钟取整到最近 5 分钟，溢出则进位
          const roundedMinutes = Math.round(newTime.minute / 5) * 5;
          let hour = newTime.hour;
          let minute = roundedMinutes;
          if (roundedMinutes === 60) {
            hour = (hour + 1) % 24;
            minute = 0;
          }
          const hh = String(hour).padStart(2, '0');
          const mm = String(minute).padStart(2, '0');
          onChange(`${hh}:${mm}`);
        }}
      >
        <TimeField.Group>
          <TimeField.Input>
            {(segment) => <TimeField.Segment segment={segment} />}
          </TimeField.Input>
        </TimeField.Group>
      </TimeField>
    );
  }

  const inputType = controlType === 'number' ? 'number' : 'text';

  return (
    <Input
      id={controlId}
      type={inputType}
      fullWidth
      value={value}
      disabled={disabled || !schema?.isEditable}
      onChange={(event) => onChange(event.target.value)}
      className={'bg-[hsl(var(--background))] shadow-[unset]'}
    />
  );
}

export const SettingsField: React.FC<SettingsFieldProps> = ({
  item,
  value,
  disabled = false,
  onChange,
  issues = [],
}) => {
  const schema = item.schema;
  const isMultiValue = isMultiValueField(item);
  const title = getFieldTitleZh(item.key, item.key);
  const description = getFieldDescriptionZh(item.key, schema?.description);
  const hasError = issues.some((issue) => issue.severity === 'error');
  const [isPasswordEditable, setIsPasswordEditable] = useState(false);
  const [visiblePasswordInputIds, setVisiblePasswordInputIds] = useState<Set<string>>(() => new Set());
  const controlId = `setting-${item.key}`;
  const togglePasswordVisibility = (inputId: string) => {
    setVisiblePasswordInputIds((current) => {
      const next = new Set(current);
      if (next.has(inputId)) {
        next.delete(inputId);
      } else {
        next.add(inputId);
      }
      return next;
    });
  };

  return (
    <div
      className={cn(
        'rounded-[1.15rem] bg-[var(--settings-surface)] p-4 transition-[background-color,border-color] duration-200',
        hasError ? 'border border-danger/40 hover:border-danger/55' : '',
        'hover:bg-[var(--settings-surface-hover)]',
      )}
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <label className="text-sm font-semibold text-foreground" htmlFor={controlId}>
          {title}
        </label>
        {schema?.isSensitive ? (
          <Badge color="warning" variant="soft" size="sm">
            敏感
          </Badge>
        ) : null}
        {!schema?.isEditable ? (
          <Badge color="default" variant="soft" size="sm">
            只读
          </Badge>
        ) : null}
      </div>

      {description ? (
        <p className="text-xs leading-5 text-muted-text">
          {description}
        </p>
        // <Tooltip delay={0}>
        //   <Tooltip.Trigger className="mb-3 inline-flex max-w-full">
        //     <p className="text-xs leading-5 text-muted-text">
        //       {description}
        //     </p>
        //   </Tooltip.Trigger>
        //   <Tooltip.Content>
        //     <p className="text-xs">{description}</p>
        //   </Tooltip.Content>
        // </Tooltip>
      ) : null}

      <div>
        {renderFieldControl(
          item,
          value,
          disabled,
          (nextValue) => onChange(item.key, nextValue),
          isPasswordEditable,
          () => setIsPasswordEditable(true),
          controlId,
          visiblePasswordInputIds,
          togglePasswordVisibility,
        )}
      </div>

      {schema?.isSensitive ? (
        <p className="mt-3 text-[11px] leading-5 text-secondary-text">
          敏感内容默认隐藏，可点击眼睛图标查看明文。
          {isMultiValue ? ' 支持添加多个输入框进行增删。' : ''}
        </p>
      ) : null}

      {issues.length ? (
        <div className="mt-2 space-y-1">
          {issues.map((issue, index) => (
            <p
              key={`${issue.code}-${issue.key}-${index}`}
              className={issue.severity === 'error' ? 'text-xs text-danger' : 'text-xs text-warning'}
            >
              {issue.message}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
};

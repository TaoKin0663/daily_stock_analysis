import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SettingsField } from '../SettingsField';

describe('SettingsField', () => {
  it('renders sensitive field metadata, validation errors, and visibility toggle', () => {
    const onChange = vi.fn();

    const { container } = render(
      <SettingsField
        item={{
          key: 'OPENAI_API_KEY',
          value: 'secret',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'OPENAI_API_KEY',
            category: 'ai_model',
            dataType: 'string',
            uiControl: 'password',
            isSensitive: true,
            isRequired: true,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        }}
        value="secret"
        onChange={onChange}
        issues={[
          {
            key: 'OPENAI_API_KEY',
            code: 'required',
            message: 'API Key is required',
            severity: 'error',
          },
        ]}
      />
    );

    expect(screen.getByText('API Key is required')).toBeInTheDocument();

    const input = screen.getByLabelText('OpenAI API Key');
    expect(input).toHaveAttribute('type', 'password');

    const toggleButton = container.querySelector('button');
    expect(toggleButton).not.toBeNull();

    fireEvent.click(toggleButton as HTMLButtonElement);
    expect(input).toHaveAttribute('type', 'text');

    fireEvent.click(toggleButton as HTMLButtonElement);
    expect(input).toHaveAttribute('type', 'password');

    fireEvent.focus(input);
    fireEvent.change(input, {
      target: { value: 'updated-secret' },
    });

    expect(onChange).toHaveBeenCalledWith('OPENAI_API_KEY', 'updated-secret');
  });

  it('renders multi-value sensitive fields with independent toggles and external delete actions', () => {
    const onChange = vi.fn();

    const { container } = render(
      <SettingsField
        item={{
          key: 'OPENAI_API_KEYS',
          value: 'secret-a,secret-b',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'OPENAI_API_KEYS',
            category: 'ai_model',
            dataType: 'string',
            uiControl: 'password',
            isSensitive: true,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: { multiValue: true },
            displayOrder: 1,
          },
        }}
        value="secret-a,secret-b"
        onChange={onChange}
      />
    );

    const buttons = Array.from(container.querySelectorAll('button'));
    const visibilityButtons = buttons.filter((button) => button.hasAttribute('aria-label'));
    expect(visibilityButtons).toHaveLength(2);

    const inputs = screen.getAllByDisplayValue(/secret-/);
    fireEvent.click(visibilityButtons[1]);

    expect(inputs[0]).toHaveAttribute('type', 'password');
    expect(inputs[1]).toHaveAttribute('type', 'text');
  });
});

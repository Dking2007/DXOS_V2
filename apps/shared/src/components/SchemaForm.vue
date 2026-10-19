<script setup lang="ts">
import type { FormField } from '../types'
const props = defineProps<{
  fields: FormField[]
  modelValue: Record<string, unknown>
  errors?: Record<string, string>
  disabled?: boolean
  readonly?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown>]
}>()
function update(field: FormField, event: Event) {
  const element = event.target as HTMLInputElement
  const value =
    field.type === 'checkbox'
      ? element.checked
      : field.type === 'number'
        ? element.value === ''
          ? null
          : Number(element.value)
        : element.value
  emit('update:modelValue', { ...props.modelValue, [field.key]: value })
}
</script>
<template>
  <div class="schema-form">
    <div
      v-for="field in fields"
      :key="field.key"
      class="field"
      :class="{ 'full-width': field.type === 'textarea' }"
    >
      <label :for="`field-${field.key}`"
        >{{ field.label
        }}<span v-if="field.required && !readonly" class="required">
          *</span
        ></label
      >
      <template v-if="readonly"
        ><p class="readonly-value">
          {{
            field.type === 'checkbox'
              ? modelValue[field.key]
                ? 'Có'
                : 'Không'
              : (modelValue[field.key] ?? '—')
          }}
        </p></template
      >
      <template v-else>
        <textarea
          v-if="field.type === 'textarea'"
          :id="`field-${field.key}`"
          :value="String(modelValue[field.key] ?? '')"
          :disabled="disabled"
          :required="field.required"
          rows="4"
          :aria-invalid="!!errors?.[field.key]"
          :aria-describedby="
            errors?.[field.key] ? `error-${field.key}` : undefined
          "
          @input="update(field, $event)"
        />
        <select
          v-else-if="field.type === 'select'"
          :id="`field-${field.key}`"
          :value="String(modelValue[field.key] ?? '')"
          :disabled="disabled"
          :required="field.required"
          :aria-invalid="!!errors?.[field.key]"
          @change="update(field, $event)"
        >
          <option value="">Chọn {{ field.label.toLowerCase() }}</option>
          <option v-for="option in field.options" :key="option" :value="option">
            {{ option }}
          </option>
        </select>
        <input
          v-else
          :id="`field-${field.key}`"
          :type="
            field.type === 'checkbox'
              ? 'checkbox'
              : field.type === 'number'
                ? 'number'
                : field.type === 'date'
                  ? 'date'
                  : 'text'
          "
          :value="
            field.type === 'checkbox'
              ? undefined
              : String(modelValue[field.key] ?? '')
          "
          :checked="
            field.type === 'checkbox'
              ? modelValue[field.key] === true
              : undefined
          "
          :disabled="disabled"
          :required="field.required"
          :step="field.type === 'number' ? 'any' : undefined"
          :aria-invalid="!!errors?.[field.key]"
          @input="update(field, $event)"
        />
        <small
          v-if="errors?.[field.key]"
          :id="`error-${field.key}`"
          class="field-error"
          >{{ errors[field.key] }}</small
        >
      </template>
    </div>
  </div>
</template>

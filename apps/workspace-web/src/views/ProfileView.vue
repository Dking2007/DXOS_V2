<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- Your own profile: the photo and details colleagues see. Role and department stay with administrators. -->
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { Camera, Save, Trash2 } from 'lucide-vue-next'
import type { Page } from '@dx/web-shared/api.ts'
import type { Department, User } from '@dx/web-shared/types.ts'
import { api } from '../api'
import { useSession } from '../stores/session'
import { toast } from '../ui/toast'
import { roleLabel } from '../ui/labels'
import { initialsOf } from '../ui/people'
import AvatarPhoto from '../components/AvatarPhoto.vue'

const session = useSession()
const queryClient = useQueryClient()
const departments = useQuery({
  queryKey: ['departments'],
  queryFn: () => api.request<Page<Department>>('/departments'),
})
const departmentName = computed(
  () =>
    departments.data.value?.items.find(
      (item) => item.id === session.user?.department_id,
    )?.name ?? 'Chưa thuộc phòng ban',
)

const FIELDS = [
  'display_name',
  'job_title',
  'phone',
  'contact_email',
  'about',
] as const
type Field = (typeof FIELDS)[number]
const form = reactive<Record<Field, string>>({
  display_name: '',
  job_title: '',
  phone: '',
  contact_email: '',
  about: '',
})
function reset() {
  for (const key of FIELDS) form[key] = session.user?.[key] ?? ''
}
watch(() => session.user, reset, { immediate: true })
const changed = computed(() =>
  FIELDS.some((key) => form[key].trim() !== (session.user?.[key] ?? '')),
)

const PHONE = /^\+?[0-9 ().-]{6,30}$/
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
const errors = computed(() => ({
  display_name: form.display_name.trim() ? '' : 'Nhập họ và tên.',
  phone:
    form.phone.trim() && !PHONE.test(form.phone.trim())
      ? 'Chỉ gồm chữ số, dấu cách và + ( ) . -'
      : '',
  contact_email:
    form.contact_email.trim() && !EMAIL.test(form.contact_email.trim())
      ? 'Chưa đúng dạng, ví dụ: ten@coquan.gov.vn'
      : '',
}))
const valid = computed(() => !Object.values(errors.value).some(Boolean))

function adopt(value: User) {
  // The profile answer has no capabilities or CSRF token; keep the session's.
  if (session.user) session.user = { ...session.user, ...value }
  void queryClient.invalidateQueries({ queryKey: ['users'] })
}

const saving = ref(false)
async function save() {
  if (!valid.value || !changed.value) return
  saving.value = true
  try {
    const body = Object.fromEntries(
      FIELDS.map((key) => [key, form[key].trim()]),
    )
    adopt(
      await api.request<User>('/me/profile', {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    )
    toast.success('Đã lưu thông tin cá nhân.')
  } catch (error) {
    toast.error(error)
  } finally {
    saving.value = false
  }
}

const TYPES = ['image/png', 'image/jpeg', 'image/webp']
const MAX = 2 * 1024 * 1024
const picker = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
async function choose(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!TYPES.includes(file.type))
    return toast.error('Chọn ảnh PNG, JPEG hoặc WebP.')
  if (file.size > MAX)
    return toast.error('Ảnh tối đa 2 MB. Hãy chọn ảnh nhỏ hơn.')
  uploading.value = true
  try {
    const body = new FormData()
    body.append('file', file)
    adopt(await api.request<User>('/me/avatar', { method: 'PUT', body }))
    toast.success('Đã đổi ảnh đại diện.')
  } catch (error) {
    toast.error(error)
  } finally {
    uploading.value = false
  }
}
async function removePhoto() {
  uploading.value = true
  try {
    adopt(await api.request<User>('/me/avatar', { method: 'DELETE' }))
    toast.success('Đã gỡ ảnh đại diện.')
  } catch (error) {
    toast.error(error)
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div v-if="session.user" class="profile-page">
    <section class="card profile-card">
      <div class="profile-photo">
        <span class="avatar profile-avatar" aria-hidden="true"
          >{{ initialsOf(session.user.display_name)
          }}<AvatarPhoto :url="session.user.avatar_url"
        /></span>
        <div class="profile-photo-actions">
          <strong>{{ session.user.display_name }}</strong>
          <small>{{
            session.user.job_title || roleLabel(session.user.role)
          }}</small>
          <div class="row-actions">
            <button
              class="button secondary small"
              type="button"
              :disabled="uploading"
              @click="picker?.click()"
            >
              <Camera :size="15" />{{
                session.user.avatar_url ? 'Đổi ảnh' : 'Tải ảnh lên'
              }}
            </button>
            <button
              v-if="session.user.avatar_url"
              class="button ghost small"
              type="button"
              :disabled="uploading"
              @click="removePhoto"
            >
              <Trash2 :size="15" />Gỡ ảnh
            </button>
          </div>
          <small class="profile-hint"
            >PNG, JPEG hoặc WebP, tối đa 2 MB. Ảnh vuông hiển thị đẹp
            nhất.</small
          >
          <input
            ref="picker"
            class="sr-only"
            tabindex="-1"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            aria-label="Chọn ảnh đại diện"
            @change="choose"
          />
        </div>
      </div>
    </section>

    <form class="card profile-card" novalidate @submit.prevent="save">
      <h2 class="profile-title">Thông tin cá nhân</h2>
      <div class="profile-grid">
        <div class="field">
          <label for="pf-name">Họ và tên <span class="required">*</span></label>
          <input
            id="pf-name"
            v-model="form.display_name"
            maxlength="200"
            autocomplete="name"
          />
          <small v-if="errors.display_name" class="field-error">{{
            errors.display_name
          }}</small>
        </div>
        <div class="field">
          <label for="pf-title">Chức danh</label>
          <input
            id="pf-title"
            v-model="form.job_title"
            maxlength="120"
            placeholder="Ví dụ: Chuyên viên tổng hợp"
          />
        </div>
        <div class="field">
          <label for="pf-phone">Số điện thoại</label>
          <input
            id="pf-phone"
            v-model="form.phone"
            maxlength="30"
            inputmode="tel"
            autocomplete="tel"
          />
          <small v-if="errors.phone" class="field-error">{{
            errors.phone
          }}</small>
        </div>
        <div class="field">
          <label for="pf-email">Email liên hệ</label>
          <input
            id="pf-email"
            v-model="form.contact_email"
            maxlength="200"
            type="email"
            autocomplete="email"
          />
          <small v-if="errors.contact_email" class="field-error">{{
            errors.contact_email
          }}</small>
        </div>
        <div class="field full-width">
          <label for="pf-about">Giới thiệu ngắn</label>
          <textarea
            id="pf-about"
            v-model="form.about"
            rows="3"
            maxlength="500"
            placeholder="Công việc bạn phụ trách, để đồng nghiệp biết khi nào nên tìm bạn."
          />
          <small>{{ form.about.length }}/500</small>
        </div>
      </div>
      <div class="profile-footer">
        <button
          class="button ghost"
          type="button"
          :disabled="!changed || saving"
          @click="reset"
        >
          Hoàn tác
        </button>
        <button
          class="button"
          type="submit"
          :disabled="!changed || !valid || saving"
        >
          <Save :size="16" />Lưu thay đổi
        </button>
      </div>
    </form>

    <section class="card profile-card">
      <h2 class="profile-title">Tài khoản</h2>
      <p class="profile-note">
        Vai trò và phòng ban do quản trị viên thiết lập.
      </p>
      <dl class="profile-facts">
        <div>
          <dt>Vai trò</dt>
          <dd>{{ roleLabel(session.user.role) }}</dd>
        </div>
        <div>
          <dt>Phòng ban</dt>
          <dd>{{ departmentName }}</dd>
        </div>
      </dl>
    </section>
  </div>
</template>

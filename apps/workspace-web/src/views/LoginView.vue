<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { ArrowRight, LockKeyhole, ShieldCheck } from 'lucide-vue-next'
import { useRoute } from 'vue-router'
const route = useRoute()
function login() {
  window.location.assign('/workspace/v1/auth/login')
}
</script>
<template>
  <main class="login-page">
    <section class="login-story" aria-label="Desktiny">
      <div class="brand">
        <span class="brand-mark">D<span /></span
        ><span>Desktiny<small>VĂN PHÒNG SỐ</small></span>
      </div>
      <div class="login-thesis">
        <span class="eyebrow">MỘT DÒNG CHẢY CÔNG VIỆC</span>
        <h1>
          Từ tài liệu đầu tiên.<br />Đến quyết định<br /><span>cuối cùng.</span>
        </h1>
        <p>
          Hồ sơ, tài liệu và phê duyệt cùng một nơi. Mỗi thay đổi có nguồn gốc.
          Mỗi quyết định giữ trọn lịch sử.
        </p>
        <div class="login-process">
          <span>Tạo hồ sơ</span><ArrowRight :size="15" /><span
            >Chuyển duyệt</span
          ><ArrowRight :size="15" /><span>Hoàn tất</span>
        </div>
      </div>
      <p class="login-story-footer">
        Desktiny · Văn phòng điện tử · Bản thử nghiệm
      </p>
    </section>
    <section class="login-form-side">
      <div class="login-form">
        <span class="eyebrow">CHÀO MỪNG TRỞ LẠI</span>
        <h2>Vào không gian làm việc</h2>
        <p>
          Sử dụng tài khoản của tổ chức để truy cập hồ sơ và tài liệu được chia
          sẻ với bạn.
        </p>
        <div
          v-if="route.query.connection"
          class="notice warning"
          style="margin-top: 20px"
        >
          Chưa kết nối được máy chủ. Kiểm tra dịch vụ backend và thử đăng nhập
          lại.
        </div>
        <button class="button" @click="login">
          Đăng nhập bằng SSO <ArrowRight :size="18" />
        </button>
        <div class="login-security">
          <LockKeyhole :size="20" /><span
            >Đăng nhập an toàn qua hệ thống định danh của tổ chức. Desktiny
            không lưu mật khẩu của bạn.</span
          >
        </div>
        <div class="notice" style="margin-top: 26px">
          <ShieldCheck :size="19" /><span
            >Nội dung hiển thị theo quyền của từng tài khoản. Liên hệ quản trị
            viên nếu bạn chưa được cấp quyền.</span
          >
        </div>
      </div>
    </section>
  </main>
</template>

import { expect, test, type Page } from '@playwright/test'

async function signIn(page: Page, username: string, password: string) {
  await page.goto('/login')
  await page.getByRole('button', { name: 'Đăng nhập bằng SSO' }).click()
  await page.locator('#username').fill(username)
  await page.locator('#password').fill(password)
  await page.locator('#kc-login').click()
  await expect(page).toHaveURL(/\/home/)
}

test('unauthenticated client is redirected to the SSO entry screen', async ({
  page,
}) => {
  await page.goto('/cases')
  await expect(page).toHaveURL(/\/login/)
  await expect(
    page.getByRole('button', { name: 'Đăng nhập bằng SSO' }),
  ).toBeVisible()
})

test('seeded staff creates a dossier and sees a persisted revision', async ({
  page,
}) => {
  test.skip(
    !process.env.DX_E2E_STAFF_USERNAME || !process.env.DX_E2E_PASSWORD,
    'Requires running Keycloak/Workspace, seeded form and explicit E2E credentials.',
  )
  await signIn(
    page,
    process.env.DX_E2E_STAFF_USERNAME!,
    process.env.DX_E2E_PASSWORD!,
  )
  await page.getByRole('link', { name: 'Hồ sơ', exact: true }).click()
  await page
    .getByRole('button', { name: 'Tạo hồ sơ', exact: true })
    .first()
    .click()
  await page.getByLabel('Tên hồ sơ').fill(`E2E hồ sơ ${Date.now()}`)
  await page.getByLabel('Mẫu hồ sơ').selectOption({ index: 1 })
  const required = page.locator(
    'dialog .schema-form input[required]:not([type="checkbox"])',
  )
  for (let index = 0; index < (await required.count()); index++) {
    const input = required.nth(index)
    const type = await input.getAttribute('type')
    await input.fill(
      type === 'number'
        ? '100'
        : type === 'date'
          ? '2026-10-18'
          : 'Nội dung kiểm thử',
    )
  }
  await page.getByRole('button', { name: 'Tạo bản nháp' }).click()
  await expect(page).toHaveURL(/\/cases\/[a-z0-9-]+/)
  await expect(
    page.getByRole('heading', { name: 'Thông tin hồ sơ' }),
  ).toBeVisible()
  await expect(page.locator('.page-head .status-badge')).toHaveText(/Bản nháp/)
  await page.reload()
  await expect(page.getByRole('heading', { name: /E2E hồ sơ/ })).toBeVisible()
})

test('staff cannot open technical audit without an explicit technical role', async ({
  page,
}) => {
  test.skip(
    !process.env.DX_E2E_STAFF_USERNAME || !process.env.DX_E2E_PASSWORD,
    'Requires running stack and explicit E2E credentials.',
  )
  await signIn(
    page,
    process.env.DX_E2E_STAFF_USERNAME!,
    process.env.DX_E2E_PASSWORD!,
  )
  const response = await page.request.get('/core/v1/audit-logs')
  expect([401, 403]).toContain(response.status())
})

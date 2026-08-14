import { test, expect } from '@playwright/test';

test.setTimeout(60000);

const gotoApp = async (page) => {
  await page.goto('/');
  await expect(page.locator('h1', { hasText: 'Choose the way your research question starts.' })).toBeVisible();
};

const primaryNav = (page) => page.locator('.app-navigation');

const openPrimaryWorkflow = async (page, label, expectedHeading) => {
  await primaryNav(page).getByRole('button', { name: label }).click();
  await expect(page.locator('h1', { hasText: expectedHeading })).toBeVisible();
};

const openAdvancedTab = async (page, tabLabel, expectedLocator) => {
  await page.getByRole('button', { name: 'Advanced tools' }).click();
  await expect(page.locator('.tabs-row')).toBeVisible();
  await page.getByRole('button', { name: tabLabel }).click();
  await expect(expectedLocator).toBeVisible();
};

test.describe('workflow-first navigation', () => {
  test('landing page renders home mode and all primary workflows', async ({ page }) => {
    await gotoApp(page);
    for (const label of [
      'Home',
      'Start from a gene',
      'Start from a list',
      'Start from a phenotype',
      'Decide and hand off',
      'Advanced tools',
    ]) {
      await expect(primaryNav(page).getByRole('button', { name: label })).toBeVisible();
    }
  });

  test('home cards navigate into the new workflow entry modes', async ({ page }) => {
    await gotoApp(page);
    await page.getByRole('button', { name: 'Start from a gene Known target exploration: network, expression, perturbation, orthology, and assay follow-up.' }).click();
    await expect(page.locator('h1', { hasText: 'Explore a known target and choose the next action.' })).toBeVisible();
  });

  test('primary navigation switches across workflow modes and updates the URL', async ({ page }) => {
    await gotoApp(page);

    await openPrimaryWorkflow(page, 'Start from a gene', 'Explore a known target and choose the next action.');
    await expect(page).toHaveURL(/view=gene/);

    await openPrimaryWorkflow(page, 'Start from a list', 'Normalize, map, interpret, and rank a user-provided gene set.');
    await expect(page).toHaveURL(/view=dataset/);

    await openPrimaryWorkflow(page, 'Start from a phenotype', 'Move from phenotype or intervention goal to species-grounded candidate genes.');
    await expect(page).toHaveURL(/view=phenotype/);

    await openPrimaryWorkflow(page, 'Decide and hand off', 'Turn current evidence into a recommendation, next step, and handoff artifact.');
    await expect(page).toHaveURL(/view=decision/);
  });

  test('artifact drawer opens from the shared action rail', async ({ page }) => {
    await gotoApp(page);
    await page.getByTitle('Open the current workflow artifacts').click();
    await expect(page.locator('.artifact-drawer.open')).toBeVisible();
    await expect(page.locator('h2', { hasText: 'Current workflow outputs' })).toBeVisible();
    await expect(page.locator('.artifact-card', { hasText: 'First-pass interpretation' })).toBeVisible();
    await page.locator('.artifact-close').click();
    await expect(page.locator('.artifact-drawer.open')).toHaveCount(0);
  });
});

test.describe('workflow panels', () => {
  test('dataset workflow shows the hit-list import entry point', async ({ page }) => {
    await gotoApp(page);
    await openPrimaryWorkflow(page, 'Start from a list', 'Normalize, map, interpret, and rank a user-provided gene set.');
    await expect(page.locator('h2', { hasText: '3. Import a hit list' })).toBeVisible();
    await expect(page.locator('textarea[placeholder*="TP53"]')).toBeVisible();
  });

  test('phenotype workflow shows literature-first ideation', async ({ page }) => {
    await gotoApp(page);
    await openPrimaryWorkflow(page, 'Start from a phenotype', 'Move from phenotype or intervention goal to species-grounded candidate genes.');
    await expect(page.locator('h2', { hasText: '2. Start from a phenotype question' })).toBeVisible();
    await expect(page.getByPlaceholder('Which genes are the best targets for changing flower color in this species?')).toBeVisible();
  });

  test('decision workflow shows planner controls', async ({ page }) => {
    await gotoApp(page);
    await openPrimaryWorkflow(page, 'Decide and hand off', 'Turn current evidence into a recommendation, next step, and handoff artifact.');
    await expect(page.locator('h2', { hasText: '5. Convert evidence into an execution plan' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Build study plan' })).toBeVisible();
  });

  test('top-level dsRNA action opens the modal shell', async ({ page }) => {
    await gotoApp(page);
    await page.getByTitle('Design a dsRNA / predict RNAi silencing + off-targets').click();
    await expect(page.locator('h2', { hasText: 'Design a dsRNA (RNAi)' })).toBeVisible();
    await expect(page.getByPlaceholder('target gene — type a name (e.g. AN2)')).toBeVisible();
  });
});

test.describe('advanced tools', () => {
  test('advanced mode exposes the legacy tab set', async ({ page }) => {
    await gotoApp(page);
    await page.getByRole('button', { name: 'Advanced tools' }).click();
    for (const label of ['Explorer', 'Organism', 'Paths', 'Orthology', 'Genome', 'Design', 'Lab']) {
      await expect(page.getByRole('button', { name: label })).toBeVisible();
    }
  });

  test('organism and lab views load through the new navigation model', async ({ page }) => {
    await gotoApp(page);
    await openAdvancedTab(page, 'Organism', page.locator('.organism-view'));
    await openAdvancedTab(page, 'Lab', page.locator('.analysis-view'));
  });

  test('analysis lab still exposes the major panel families', async ({ page }) => {
    await gotoApp(page);
    await openAdvancedTab(page, 'Lab', page.locator('.analysis-view'));
    for (const section of ['Regulon & Upstream', 'Network Structure', 'Inference & Comparison', 'Export']) {
      await expect(page.locator('.analysis-section-title', { hasText: section })).toBeVisible();
    }
  });
});

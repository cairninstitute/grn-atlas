import { test, expect } from '@playwright/test';

test.setTimeout(60000);

const gotoApp = async (page) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'What do you want to understand?' })).toBeVisible();
};

const primaryNav = (page) => page.getByRole('tablist', { name: 'Primary workflows' });

const openPrimaryWorkflow = async (page, label, expectedView) => {
  await primaryNav(page).getByRole('button', { name: label }).click();
  await expect(page).toHaveURL(new RegExp(`view=${expectedView}`));
};

const openActions = async (page) => {
  await page.getByText('Actions', { exact: true }).click();
  await expect(page.locator('.workspace-actions-menu')).toBeVisible();
};

test.describe('question-led navigation', () => {
  test('landing page renders the current primary workflows and live atlas summary', async ({ page }) => {
    await gotoApp(page);
    for (const label of ['Home', 'Explore networks', 'Design experiments', 'Analysis tools']) {
      await expect(primaryNav(page).getByRole('button', { name: label })).toBeVisible();
    }
    await expect(page.getByRole('complementary', { name: 'Atlas summary' })).toContainText('species');
    await expect(page.getByRole('button', { name: /Understand a regulatory neighborhood/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Find feedback and control systems/ })).toBeVisible();
  });

  test('home research paths open the corresponding workspaces', async ({ page }) => {
    await gotoApp(page);
    await page.getByRole('button', { name: /Understand a regulatory neighborhood/ }).click();
    await expect(page).toHaveURL(/view=network/);
    await expect(page.getByText('Gene regulatory neighborhood', { exact: true })).toBeVisible();

    await primaryNav(page).getByRole('button', { name: 'Home' }).click();
    await page.getByRole('button', { name: /Find feedback and control systems/ }).click();
    await expect(page).toHaveURL(/view=feedback/);
    await expect(page.getByText('Feedback and control systems', { exact: true })).toBeVisible();
  });

  test('primary navigation switches among explore, design, and analysis tools', async ({ page }) => {
    await gotoApp(page);

    await openPrimaryWorkflow(page, 'Explore networks', 'network');
    await expect(page.getByRole('tab', { name: 'Gene network' })).toHaveAttribute('aria-selected', 'true');

    await openPrimaryWorkflow(page, 'Design experiments', 'intervention');
    await expect(page.getByText('Select a target before planning an intervention')).toBeVisible();

    await openPrimaryWorkflow(page, 'Analysis tools', 'toolbox');
    await expect(page.getByRole('heading', { name: 'Choose an analysis by the question it answers.' })).toBeVisible();
  });

  test('featured control-architecture demonstration opens and returns home', async ({ page }) => {
    await gotoApp(page);
    await page.getByRole('button', { name: /Featured guided demonstration/ }).click();
    await expect(page).toHaveURL(/view=control-demo/);
    await expect(page.getByRole('heading', { name: 'From millions of interactions to biological control architecture' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'AP3–PI–SUP maintains the stamen–carpel boundary' })).toBeVisible();
    await page.getByRole('button', { name: 'Darwin home' }).click();
    await expect(page.getByRole('heading', { name: 'What do you want to understand?' })).toBeVisible();
  });

  test('generated-output drawer opens from the workspace action menu', async ({ page }) => {
    await gotoApp(page);
    await openPrimaryWorkflow(page, 'Explore networks', 'network');
    await openActions(page);
    await page.getByRole('button', { name: 'View generated outputs' }).click();
    await expect(page.locator('.artifact-drawer.open')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Current workflow outputs' })).toBeVisible();
    await page.locator('.artifact-close').click();
    await expect(page.locator('.artifact-drawer.open')).toHaveCount(0);
  });
});

test.describe('research workspaces', () => {
  test('whole-species feedback view loads from the home journey', async ({ page }) => {
    await gotoApp(page);
    await page.getByRole('button', { name: /Find feedback and control systems/ }).click();
    await expect(page.locator('.feedback-view')).toBeVisible();
    await expect(page.getByText('Feedback and control systems', { exact: true })).toBeVisible();
  });

  test('CloneLab loads from the molecular-validation journey', async ({ page }) => {
    await gotoApp(page);
    await page.getByRole('button', { name: /Build and verify a DNA construct/ }).click();
    await expect(page).toHaveURL(/view=clonelab/);
    await expect(page.locator('.clonelab-workspace')).toBeVisible();
  });

  test('gene-list analysis remains available from home', async ({ page }) => {
    await gotoApp(page);
    await page.getByRole('button', { name: 'Analyze a gene list instead' }).click();
    await expect(page.getByRole('heading', { name: 'Gene-set analysis' })).toBeVisible();
  });

  test('dsRNA design remains available from workspace actions', async ({ page }) => {
    await gotoApp(page);
    await openPrimaryWorkflow(page, 'Explore networks', 'network');
    await openActions(page);
    await page.getByRole('button', { name: 'Design dsRNA' }).click();
    await expect(page.getByRole('heading', { name: 'Design a dsRNA (RNAi)' })).toBeVisible();
    await expect(page.getByPlaceholder('target gene — type a name (e.g. AN2)')).toBeVisible();
  });

  test('explore mode exposes the renamed biological views', async ({ page }) => {
    await gotoApp(page);
    await openPrimaryWorkflow(page, 'Explore networks', 'network');
    for (const label of [
      'Gene network',
      'Control systems',
      'Species overview',
      'Cross-species',
      'Regulatory paths',
      'Orthologs',
      'Genome context',
      'TF landscape',
    ]) {
      await expect(page.getByRole('tab', { name: label })).toBeVisible();
    }
  });

  test('design mode exposes intervention comparison and CloneLab', async ({ page }) => {
    await gotoApp(page);
    await openPrimaryWorkflow(page, 'Design experiments', 'intervention');
    for (const label of ['Choose an intervention', 'Compare CRISPR / RNAi', 'Build & verify DNA']) {
      await expect(page.getByRole('tab', { name: label })).toBeVisible();
    }
  });
});

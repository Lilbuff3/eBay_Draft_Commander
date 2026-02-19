export enum WorkflowStage {
    IMPORT = 0,
    ANALYZE = 1,
    EDIT = 2,
    PRICE = 3,
    POST = 4,
}

export const stages = [
    { id: WorkflowStage.IMPORT, label: 'Import' },
    { id: WorkflowStage.ANALYZE, label: 'Analyze' },
    { id: WorkflowStage.EDIT, label: 'Edit' },
    { id: WorkflowStage.PRICE, label: 'Price' },
    { id: WorkflowStage.POST, label: 'Post' },
]

export interface OperationPart {
  id: string;
  type: 'step-start' | 'reasoning';
  text: string;
}

export function getVisibleOperations(
  operations: OperationPart[],
  expanded: boolean,
  defaultVisible = 3,
): OperationPart[] {
  if (expanded) {
    return operations;
  }
  return operations.slice(0, defaultVisible);
}

export function shouldShowExpandOperations(
  operations: OperationPart[],
  defaultVisible = 3,
): boolean {
  return operations.length > defaultVisible;
}

export function shouldSendMessageOnKeyDown(event: {
  key: string;
  metaKey: boolean;
  shiftKey: boolean;
  isComposing?: boolean;
}): boolean {
  if (event.isComposing) {
    return false;
  }
  return event.key === 'Enter' && event.metaKey && !event.shiftKey;
}

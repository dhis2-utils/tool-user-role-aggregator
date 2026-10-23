interface ErrorReport {
    message?: string
}

interface ImportReportDetails {
    response?: {
        errorReports?: ErrorReport[]
    }
}

/**
 * The most useful message from a failed mutation. On a 409 the data engine's
 * message is only "One or more errors occurred"; the reason, such as a role
 * name that is already taken, is in the import report's error reports.
 */
export const mutationErrorMessage = (error: Error): string => {
    const { details } = error as Error & { details?: ImportReportDetails }
    const reports = (details?.response?.errorReports ?? [])
        .map((report) => report.message)
        .filter((message): message is string => Boolean(message))
    return reports.length > 0 ? reports.join(' ') : error.message
}

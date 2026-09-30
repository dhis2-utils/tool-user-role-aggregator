import React from 'react'

const style: React.CSSProperties = {
    maxInlineSize: '1400px',
    marginInlineStart: 'auto',
    marginInlineEnd: 'auto',
    padding: '20px 16px',
    inlineSize: '100%',
}

export const PageWrapper = ({ children }: { children: React.ReactNode }) => (
    <div style={style}>{children}</div>
)

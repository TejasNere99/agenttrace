import { type ButtonHTMLAttributes, type ReactNode } from 'react'
import { motion } from 'framer-motion'

export function Button({ children, variant = 'secondary', className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost'; children: ReactNode }) {
  return <button className={`button button-${variant} ${className}`} {...props}>{children}</button>
}
export function Card({ children, className = '', id }: { children: ReactNode; className?: string; id?: string }) { return <motion.section id={id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .28 }} className={`card ${className}`}>{children}</motion.section> }
export function Badge({ status, children }: { status: string; children?: ReactNode }) { return <span className={`badge badge-${status.toLowerCase()}`}><i />{children ?? status}</span> }
export function PageTitle({ title, subtitle, action }: { title: string; subtitle: ReactNode; action?: ReactNode }) { return <div className="page-title"><div><h1>{title}</h1><p>{subtitle}</p></div>{action && <div className="page-action">{action}</div>}</div> }
export function EmptyState({ title, text }: { title: string; text: string }) { return <div className="empty-state"><span>◌</span><strong>{title}</strong><p>{text}</p></div> }

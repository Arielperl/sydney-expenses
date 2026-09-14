import { http, HttpResponse } from 'msw'
import { describe, it, expect } from 'vitest'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { AuthProvider, RequireAuth } from '../../contexts/AuthContext'
import { AuthPage } from '../AuthPage'
import { renderWithProviders, screen } from '../../test/test-utils'
import { server } from '../../test/msw/server'
const base='http://localhost:8000/api/auth'
function setup(route='/login') {
 server.use(http.get(`${base}/session`,()=>HttpResponse.json({detail:'unauthorized'},{status:401})),http.post(`${base}/refresh`,()=>HttpResponse.json({detail:'unauthorized'},{status:401})))
 return renderWithProviders(<AuthProvider><Routes><Route path="/login" element={<AuthPage mode="login"/>}/><Route path="/signup" element={<AuthPage mode="signup"/>}/><Route element={<RequireAuth/>}><Route path="/app" element={<div>Private dashboard</div>}/></Route></Routes></AuthProvider>,{route})
}
describe('Authentication flow',()=>{
 it('redirects an anonymous visitor to login',async()=>{setup('/app');expect(await screen.findByRole('heading',{name:'מתחברים לתמונה המלאה.'})).toBeInTheDocument();expect(screen.queryByText('Private dashboard')).not.toBeInTheDocument()})
 it('shows email verification after signup and does not open workspace',async()=>{
  setup('/signup');server.use(http.post(`${base}/signup`,()=>HttpResponse.json({confirmation_required:true,user:null})))
  const u=userEvent.setup();await u.type(screen.getByLabelText('השם שלכם'),'Ariel');await u.type(screen.getByLabelText('כתובת אימייל'),'a@example.com');await u.type(screen.getByLabelText('סיסמה'),'strongpassword');await u.click(screen.getByRole('button',{name:'יצירת חשבון'}));expect(await screen.findByRole('status')).toHaveTextContent('קישור לאימות');expect(screen.queryByText('Private dashboard')).not.toBeInTheDocument()
 })
 it('opens workspace after a valid owner login',async()=>{
  setup();server.use(http.post(`${base}/login`,()=>HttpResponse.json({user:{id:'1',email:'a@example.com',name:'Ariel',has_workspace:true}})))
  const u=userEvent.setup();await u.type(screen.getByLabelText('כתובת אימייל'),'a@example.com');await u.type(screen.getByLabelText('סיסמה'),'password');await u.click(screen.getByRole('button',{name:'כניסה למערכת'}));expect(await screen.findByText('Private dashboard')).toBeInTheDocument()
 })
 it('shows errors without granting access',async()=>{
  setup();server.use(http.post(`${base}/login`,()=>HttpResponse.json({detail:'פרטי ההתחברות אינם נכונים'},{status:401})))
  const u=userEvent.setup();await u.type(screen.getByLabelText('כתובת אימייל'),'a@example.com');await u.type(screen.getByLabelText('סיסמה'),'password');await u.click(screen.getByRole('button',{name:'כניסה למערכת'}));expect(await screen.findByRole('alert')).toHaveTextContent('פרטי ההתחברות אינם נכונים');expect(screen.queryByText('Private dashboard')).not.toBeInTheDocument()
 })
 it('keeps newly registered users outside existing business data',async()=>{
  setup();server.use(http.post(`${base}/login`,()=>HttpResponse.json({user:{id:'2',email:'other@example.com',name:'Other',has_workspace:false}})))
  const u=userEvent.setup();await u.type(screen.getByLabelText('כתובת אימייל'),'other@example.com');await u.type(screen.getByLabelText('סיסמה'),'password');await u.click(screen.getByRole('button',{name:'כניסה למערכת'}));expect(await screen.findByText(/נכיר את העסק שלכם/)).toBeInTheDocument();expect(screen.queryByText('Private dashboard')).not.toBeInTheDocument()
 })
})

it('creates a private business and enters the workspace after the server confirms membership', async () => {
 let created = false
 const user = { id: 'new', email: 'new@example.com', name: 'New' }
 server.use(
  http.get(`${base}/session`, () => HttpResponse.json({ user: { ...user, has_workspace: created } })),
  http.post('http://localhost:8000/api/businesses', async ({ request }) => {
   expect(await request.json()).toEqual({ name: 'החנות שלי', business_number: null })
   created = true
   return HttpResponse.json({ id: 'private-business', name: 'החנות שלי' }, { status: 201 })
  }),
 )
 renderWithProviders(<AuthProvider><Routes><Route element={<RequireAuth/>}><Route path="/app" element={<div>Private dashboard</div>}/></Route></Routes></AuthProvider>,{route:'/app'})
 const u = userEvent.setup()
 await u.type(await screen.findByLabelText('שם העסק'), 'החנות שלי')
 await u.click(screen.getByRole('button', { name: 'יצירת העסק וכניסה למערכת' }))
 expect(await screen.findByText('Private dashboard')).toBeInTheDocument()
})

import { NextResponse } from 'next/server'
import { readFileSync } from 'fs'
import { join } from 'path'

export async function GET() {
  try {
    // Next.js process.cwd() is the frontend directory, terms is in parent
    const filePath = join(process.cwd(), '../terms/privacy_policy.txt')
    console.log('Attempting to read privacy policy from:', filePath)
    const content = readFileSync(filePath, 'utf-8')
    
    return new NextResponse(content, {
      headers: {
        'Content-Type': 'text/plain',
      },
    })
  } catch (error) {
    console.error('Error reading privacy policy:', error)
    return new NextResponse('Privacy Policy is currently unavailable. Please contact support@baseballpath.com for more information.', {
      status: 500,
      headers: {
        'Content-Type': 'text/plain',
      },
    })
  }
}
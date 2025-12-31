#!/usr/bin/env python3
"""Debug Polymarket API to understand actual response structure."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import httpx

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


async def investigate_polymarket_api():
    """Investigate the actual Polymarket API response structure."""
    
    base_urls = [
        "https://gamma-api.polymarket.com",
        "https://clob.polymarket.com", 
        "https://api.polymarket.com"
    ]
    
    endpoints = [
        "/markets",
        "/events", 
        "/conditions",
        "/markets?active=true&limit=5"
    ]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        
        for base_url in base_urls:
            logger.info(f"\n🔍 Testing API: {base_url}")
            
            for endpoint in endpoints:
                try:
                    url = f"{base_url}{endpoint}"
                    logger.info(f"  📡 GET {url}")
                    
                    response = await client.get(url)
                    logger.info(f"  📊 Status: {response.status_code}")
                    
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            logger.info(f"  📄 Response type: {type(data)}")
                            
                            if isinstance(data, list):
                                logger.info(f"  📋 Array with {len(data)} items")
                                if data:
                                    logger.info(f"  🎯 First item keys: {list(data[0].keys())}")
                                    
                                    # Save sample for analysis
                                    sample_file = Path(__file__).parent.parent / f"polymarket_sample_{base_url.split('//')[1].split('.')[0]}_{endpoint.replace('/', '_').replace('?', '_')}.json"
                                    with open(sample_file, 'w') as f:
                                        json.dump(data[:3], f, indent=2)  # Save first 3 items
                                    logger.info(f"  💾 Sample saved to: {sample_file.name}")
                                    
                            elif isinstance(data, dict):
                                logger.info(f"  📋 Object with keys: {list(data.keys())}")
                                
                                # Check if it contains market data
                                if 'data' in data or 'markets' in data or 'events' in data:
                                    markets_data = data.get('data', data.get('markets', data.get('events', [])))
                                    if markets_data and isinstance(markets_data, list):
                                        logger.info(f"  🎯 Markets array with {len(markets_data)} items")
                                        if markets_data:
                                            logger.info(f"  🎯 First market keys: {list(markets_data[0].keys())}")
                                
                                # Save sample for analysis
                                sample_file = Path(__file__).parent.parent / f"polymarket_sample_{base_url.split('//')[1].split('.')[0]}_{endpoint.replace('/', '_').replace('?', '_')}.json"
                                with open(sample_file, 'w') as f:
                                    json.dump(data, f, indent=2)
                                logger.info(f"  💾 Sample saved to: {sample_file.name}")
                            
                            # Look for soccer-related content
                            content_str = str(data).lower()
                            soccer_keywords = ['soccer', 'football', 'premier', 'liga', 'goal', 'match']
                            found_keywords = [kw for kw in soccer_keywords if kw in content_str]
                            if found_keywords:
                                logger.info(f"  ⚽ Soccer content found: {found_keywords}")
                            
                        except json.JSONDecodeError as e:
                            logger.warning(f"  ❌ JSON decode error: {e}")
                            logger.info(f"  📄 Raw response (first 200 chars): {response.text[:200]}")
                    
                    else:
                        logger.warning(f"  ❌ HTTP {response.status_code}: {response.text[:100]}")
                    
                    # Small delay to be respectful
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.warning(f"  ❌ Error: {e}")
                    await asyncio.sleep(0.5)


async def test_specific_market_endpoint():
    """Test specific market endpoints that might work better."""
    
    logger.info(f"\n🎯 Testing specific market endpoints...")
    
    # Known working endpoints from Polymarket docs
    test_urls = [
        "https://gamma-api.polymarket.com/markets?limit=10&offset=0&active=true",
        "https://gamma-api.polymarket.com/events?limit=10&offset=0&active=true", 
        "https://clob.polymarket.com/markets",
        "https://clob.polymarket.com/events"
    ]
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        
        for url in test_urls:
            try:
                logger.info(f"\n📡 Testing: {url}")
                
                # Add common headers that might be expected
                headers = {
                    'User-Agent': 'Mozilla/5.0 (compatible; Soccer-MM-Bot/1.0)',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }
                
                response = await client.get(url, headers=headers)
                logger.info(f"📊 Status: {response.status_code}")
                logger.info(f"📋 Headers: {dict(response.headers)}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        # Detailed analysis
                        logger.info(f"📄 Response structure analysis:")
                        logger.info(f"  Type: {type(data)}")
                        
                        if isinstance(data, list):
                            logger.info(f"  Array length: {len(data)}")
                            if data:
                                first_item = data[0]
                                logger.info(f"  First item type: {type(first_item)}")
                                if isinstance(first_item, dict):
                                    logger.info(f"  First item keys: {list(first_item.keys())}")
                                    
                                    # Look for key fields
                                    key_fields = ['question', 'title', 'outcomes', 'tokens', 'market_slug', 'condition_id']
                                    for field in key_fields:
                                        if field in first_item:
                                            value = first_item[field]
                                            logger.info(f"    {field}: {type(value)} = {str(value)[:100]}")
                        
                        elif isinstance(data, dict):
                            logger.info(f"  Object keys: {list(data.keys())}")
                            
                            # Look for nested market data
                            for key in ['data', 'markets', 'events', 'results']:
                                if key in data:
                                    nested = data[key]
                                    logger.info(f"    {key}: {type(nested)}")
                                    if isinstance(nested, list) and nested:
                                        logger.info(f"      Array length: {len(nested)}")
                                        logger.info(f"      First item keys: {list(nested[0].keys()) if isinstance(nested[0], dict) else 'Not dict'}")
                        
                        # Save detailed sample
                        safe_name = url.replace('https://', '').replace('/', '_').replace('?', '_').replace('=', '_')
                        sample_file = Path(__file__).parent.parent / f"detailed_sample_{safe_name}.json"
                        
                        # Save a reasonable amount of data
                        sample_data = data
                        if isinstance(data, list) and len(data) > 5:
                            sample_data = data[:5]
                        elif isinstance(data, dict):
                            # If it has nested arrays, limit those too
                            sample_data = {}
                            for k, v in data.items():
                                if isinstance(v, list) and len(v) > 5:
                                    sample_data[k] = v[:5]
                                else:
                                    sample_data[k] = v
                        
                        with open(sample_file, 'w') as f:
                            json.dump(sample_data, f, indent=2)
                        logger.info(f"💾 Detailed sample saved: {sample_file.name}")
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"❌ JSON decode error: {e}")
                        # Save raw response for analysis
                        raw_file = Path(__file__).parent.parent / f"raw_response_{safe_name}.txt"
                        with open(raw_file, 'w') as f:
                            f.write(response.text)
                        logger.info(f"💾 Raw response saved: {raw_file.name}")
                
                else:
                    logger.warning(f"❌ HTTP {response.status_code}")
                    logger.info(f"📄 Response: {response.text[:200]}")
                
                await asyncio.sleep(1.0)  # Be respectful
                
            except Exception as e:
                logger.error(f"❌ Error with {url}: {e}")
                await asyncio.sleep(1.0)


async def main():
    """Main investigation function."""
    logger.info("🚀 Investigating Polymarket API structure")
    
    try:
        await investigate_polymarket_api()
        await test_specific_market_endpoint()
        
        logger.info("\n✅ Investigation complete!")
        logger.info("📁 Check the generated JSON files to understand the API structure")
        
        # List generated files
        project_root = Path(__file__).parent.parent
        sample_files = list(project_root.glob("*sample*.json")) + list(project_root.glob("*response*.txt"))
        
        if sample_files:
            logger.info("\n📋 Generated files for analysis:")
            for file in sample_files:
                logger.info(f"  - {file.name}")
        
    except Exception as e:
        logger.error(f"❌ Investigation failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
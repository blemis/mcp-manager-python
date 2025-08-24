# KID.md - Keep It Direct Plan

## Problem Statement
MCP Manager CLI commands report success but don't persist data to the database. Need to understand actual data flow and fix persistence layer.

## Investigation Plan

### Phase 1: Map Current Data Flow (30 min)
1. **Trace server add command end-to-end**
   - Follow code from `mcp-manager add` → actual storage
   - Identify all code paths and storage mechanisms
   - Document what writes where

2. **Trace suite create command end-to-end**  
   - Follow code from `mcp-manager suite create` → actual storage
   - Map suite data flow vs server data flow
   - Identify any disconnects

3. **Find all storage locations**
   - Claude MCP config files location
   - MCP Manager database usage
   - Any other config/cache files

### Phase 2: Identify Root Cause (15 min)
1. **Server operations**: Do they write to Claude config only?
2. **Suite operations**: Do they write to MCP Manager DB?
3. **Missing connections**: Are there broken links in the persistence chain?

### Phase 3: Fix Database Integration (60 min)
1. **If suite operations should use MCP Manager DB**: Fix the broken database writes
2. **If suite operations should use Claude config**: Remove unused database code
3. **If hybrid approach**: Ensure proper coordination between both systems

### Phase 4: Verification (15 min)
1. **Test server add**: Verify persistence in correct location
2. **Test suite create**: Verify persistence in correct location  
3. **Test data survives restart**: Confirm actual persistence

## Key Questions to Answer
- Where should suite data be stored? (MCP Manager DB vs Claude config)
- Why do CLI commands succeed but DB stays empty?
- Are there async/await issues preventing database writes?
- Is there a configuration issue pointing to wrong database?

## Success Criteria
- Server operations clearly documented (Claude config or DB)
- Suite operations clearly documented (Claude config or DB)  
- All reported successes actually persist data
- Data survives application restart

## Anti-Goals
- Don't fix tests until data persistence works
- Don't optimize performance until functionality works
- Don't add features until core storage works
import React, { useState } from 'react';
import { Search, Plus, MessageSquare, Settings, Download, Share, MoreHorizontal, ChevronDown, ChevronRight, Edit2, Trash2, FolderOpen, Clock, Mic } from 'lucide-react';

const ImprovedAIInterface = () => {
  const [sidebarExpanded, setSidebarExpanded] = useState(true);
  const [expandedSections, setExpandedSections] = useState({
    recent: true,
    projects: true
  });
  const [hoveredProject, setHoveredProject] = useState(null);

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const recentChats = [
    { id: 1, title: "Remove the background", model: "stable-image-core", time: "2m ago" },
    { id: 2, title: "Give me an image of a pig on a...", model: "stable-image-core", time: "5m ago" },
    { id: 3, title: "Rugby uniform design ideas", model: "stable-image-core", time: "1h ago" },
    { id: 4, title: "Create a modern logo design", model: "stable-image-core", time: "2h ago" },
    { id: 5, title: "Photo editing tutorial", model: "stable-image-core", time: "3h ago" },
    { id: 6, title: "Landscape photography tips", model: "stable-image-core", time: "5h ago" },
    { id: 7, title: "Portrait retouching workflow", model: "stable-image-core", time: "1d ago" },
    { id: 8, title: "AI art generation prompts", model: "stable-image-core", time: "1d ago" },
    { id: 9, title: "Color grading techniques", model: "stable-image-core", time: "2d ago" },
    { id: 10, title: "Digital painting basics", model: "stable-image-core", time: "2d ago" },
    { id: 11, title: "Product photography setup", model: "stable-image-core", time: "3d ago" },
    { id: 12, title: "Brand identity guidelines", model: "stable-image-core", time: "3d ago" },
  ];

  const projects = [
    { id: 1, name: "Image Processing", count: 12 },
    { id: 2, name: "Design Prototypes", count: 8 },
    { id: 3, name: "Content Generation", count: 15 },
    { id: 4, name: "Marketing Materials", count: 23 },
    { id: 5, name: "Social Media Assets", count: 34 },
    { id: 6, name: "Product Photography", count: 19 },
    { id: 7, name: "Brand Development", count: 7 },
    { id: 8, name: "Website Graphics", count: 28 },
    { id: 9, name: "Print Designs", count: 16 },
    { id: 10, name: "Video Thumbnails", count: 42 },
    { id: 11, name: "Logo Concepts", count: 31 },
    { id: 12, name: "Illustration Work", count: 25 },
  ];

  return (
    <div className="h-screen bg-gray-50 flex">
      {/* Improved Sidebar */}
      <div className={`bg-white border-r border-gray-200 transition-all duration-300 ${sidebarExpanded ? 'w-80' : 'w-16'} flex flex-col`}>
        {/* Header */}
        <div className="p-4 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <div className={`flex items-center space-x-3 ${!sidebarExpanded && 'justify-center'}`}>
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <MessageSquare className="w-5 h-5 text-white" />
              </div>
              {sidebarExpanded && (
                <div>
                  <h1 className="text-lg font-semibold text-gray-900">AI Knowledge Base</h1>
                </div>
              )}
            </div>
            <button 
              onClick={() => setSidebarExpanded(!sidebarExpanded)}
              className="w-4 h-4 hover:bg-gray-100 flex items-center justify-center"
            >
              {sidebarExpanded ? (
                <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1">
                  <rect x="1" y="2" width="14" height="12" rx="1" className="stroke-gray-400"/>
                  <line x1="5" y1="2" x2="5" y2="14" className="stroke-gray-400"/>
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg" className="text-gray-600">
                  <path d="M3.5 3C3.77614 3 4 3.22386 4 3.5V16.5L3.99023 16.6006C3.94371 16.8286 3.74171 17 3.5 17C3.25829 17 3.05629 16.8286 3.00977 16.6006L3 16.5V3.5C3 3.22386 3.22386 3 3.5 3ZM11.2471 5.06836C11.4476 4.95058 11.7104 4.98547 11.8721 5.16504C12.0338 5.34471 12.0407 5.60979 11.9023 5.79688L11.835 5.87207L7.80371 9.5H16.5C16.7761 9.5 17 9.72386 17 10C17 10.2761 16.7761 10.5 16.5 10.5H7.80371L11.835 14.1279C12.0402 14.3127 12.0568 14.6297 11.8721 14.835C11.6873 15.0402 11.3703 15.0568 11.165 14.8721L6.16504 10.3721L6.09473 10.2939C6.03333 10.2093 6 10.1063 6 10C6 9.85828 6.05972 9.72275 6.16504 9.62793L11.165 5.12793L11.2471 5.06836Z"/>
                </svg>
              )}
            </button>
          </div>
        </div>

        {sidebarExpanded && (
          <>
            {/* Search */}
            <div className="p-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search conversations, projects..."
                  className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* New Chat Button */}
            <div className="px-4 pb-4">
              <button className="w-full flex items-center justify-center space-x-2 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                <Plus className="w-4 h-4" />
                <span className="font-medium">New Chat</span>
              </button>
            </div>
          </>
        )}

        {/* Navigation Content */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {sidebarExpanded ? (
            <div className="h-full flex flex-col">
              {/* Fixed section headers and controls */}
              <div className="px-4 space-y-4 flex-shrink-0">
                {/* Recent Conversations Header */}
                <div>
                  <button
                    onClick={() => toggleSection('recent')}
                    className="flex items-center justify-between w-full py-2 text-sm font-medium text-gray-700 hover:text-gray-900"
                  >
                    <div className="flex items-center space-x-2">
                      <Clock className="w-4 h-4" />
                      <span>Recent</span>
                    </div>
                    <div className="w-4 h-4 border border-gray-400 rounded-sm flex items-center justify-center">
                      {expandedSections.recent ? 
                        <div className="w-2.5 h-0.5 bg-gray-600"></div> : 
                        <Plus className="w-2.5 h-2.5 text-gray-600" />
                      }
                    </div>
                  </button>
                </div>
              </div>

              {/* Content sections */}
              <div className="flex-1 flex flex-col px-4 min-h-0 overflow-hidden">
                {/* Recent Conversations Section */}
                {expandedSections.recent && (
                  <div className="mb-6">
                    <div className="max-h-40 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100 pr-2">
                      <div className="space-y-2">
                        {recentChats.slice(0, 6).map(chat => (
                          <div
                            key={chat.id}
                            className="group flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                            onMouseEnter={() => setHoveredProject(`recent-${chat.id}`)}
                            onMouseLeave={() => setHoveredProject(null)}
                          >
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-gray-900 truncate">
                                {chat.title}
                              </p>
                              <div className="flex items-center space-x-2 mt-1">
                                <span className="text-xs text-gray-500">{chat.model}</span>
                                <span className="text-xs text-gray-400">•</span>
                                <span className="text-xs text-gray-500">{chat.time}</span>
                              </div>
                            </div>
                            {hoveredProject === `recent-${chat.id}` && (
                              <div className="flex items-center space-x-1 ml-2">
                                <button className="p-1.5 hover:bg-gray-200 rounded-md">
                                  <Edit2 className="w-3 h-3 text-gray-500" />
                                </button>
                                <button className="p-1.5 hover:bg-gray-200 rounded-md">
                                  <Trash2 className="w-3 h-3 text-gray-500" />
                                </button>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Projects Section */}
                <div className="flex-1 min-h-0 flex flex-col">
                  <button
                    onClick={() => toggleSection('projects')}
                    className="flex items-center justify-between w-full py-2 text-sm font-medium text-gray-700 hover:text-gray-900 flex-shrink-0 mb-3"
                  >
                    <div className="flex items-center space-x-2">
                      <FolderOpen className="w-4 h-4" />
                      <span>Projects</span>
                    </div>
                    <div className="w-4 h-4 border border-gray-400 rounded-sm flex items-center justify-center">
                      {expandedSections.projects ? 
                        <div className="w-2.5 h-0.5 bg-gray-600"></div> : 
                        <Plus className="w-2.5 h-2.5 text-gray-600" />
                      }
                    </div>
                  </button>
                  
                  {expandedSections.projects && (
                    <div className="flex-1 min-h-0 flex flex-col">
                      {/* Scrollable projects list */}
                      <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100 pr-2 mb-4">
                        <div className="space-y-2">
                          {projects.map(project => (
                            <div
                              key={project.id}
                              className="group flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                              onMouseEnter={() => setHoveredProject(`project-${project.id}`)}
                              onMouseLeave={() => setHoveredProject(null)}
                            >
                              <div className="flex items-center space-x-3 flex-1 min-w-0">
                                <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                                  <FolderOpen className="w-4 h-4 text-blue-600" />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm font-medium text-gray-900 truncate">
                                    {project.name}
                                  </p>
                                  <p className="text-xs text-gray-500">
                                    {project.count} conversations
                                  </p>
                                </div>
                              </div>
                              {hoveredProject === `project-${project.id}` && (
                                <div className="flex items-center space-x-1 ml-2">
                                  <button className="p-1.5 hover:bg-gray-200 rounded-md">
                                    <Edit2 className="w-3 h-3 text-gray-500" />
                                  </button>
                                  <button className="p-1.5 hover:bg-gray-200 rounded-md">
                                    <Trash2 className="w-3 h-3 text-gray-500" />
                                  </button>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                        
                      {/* New Project Button - Always visible and well-designed */}
                      <div className="flex-shrink-0 pt-3 border-t border-gray-200">
                        <button className="w-full group flex items-center justify-center space-x-2 p-4 text-sm text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-xl border border-blue-200 hover:border-blue-300 transition-all duration-200 font-medium shadow-sm">
                          <div className="w-5 h-5 rounded-full bg-blue-600 group-hover:bg-blue-700 flex items-center justify-center transition-colors">
                            <Plus className="w-3 h-3 text-white" />
                          </div>
                          <span>New Project</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            // Collapsed sidebar icons
            <div className="px-2 space-y-2">
              <button className="w-12 h-12 flex items-center justify-center rounded-lg hover:bg-gray-100">
                <Clock className="w-5 h-5 text-gray-600" />
              </button>
              <button className="w-12 h-12 flex items-center justify-center rounded-lg hover:bg-gray-100">
                <FolderOpen className="w-5 h-5 text-gray-600" />
              </button>
            </div>
          )}
        </div>

        {/* Bottom Settings */}
        {sidebarExpanded && (
          <div className="p-4 border-t border-gray-100">
            <button className="w-full flex items-center space-x-3 p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-lg">
              <Settings className="w-4 h-4" />
              <span className="text-sm">Settings</span>
            </button>
          </div>
        )}
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Top Bar */}
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <select className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option>Stable Image Core</option>
                <option>DALL-E 3</option>
                <option>Midjourney</option>
              </select>
            </div>
            <div className="flex items-center space-x-2">
              <button className="p-2 bg-gray-100 hover:bg-gray-200 rounded-lg border border-gray-200" title="Context Panel">
                <svg className="w-4 h-4 text-gray-600" fill="currentColor" viewBox="0 0 512 512">
                  <path d="M232 120C232 106.7 242.7 96 256 96s24 10.7 24 24c0 13.3-10.7 24-24 24s-24-10.7-24-24zM464 336c26.5 0 48 21.5 48 48v32c0 26.5-21.5 48-48 48H48c-26.5 0-48-21.5-48-48V384c0-26.5 21.5-48 48-48H64V128c0-35.3 28.7-64 64-64H384c35.3 0 64 28.7 64 64V336h16zm-80 0V128c0-8.8-7.2-16-16-16H144c-8.8 0-16 7.2-16 16V336H384zM176 208c0-8.8 7.2-16 16-16h128c8.8 0 16 7.2 16 16s-7.2 16-16 16H192c-8.8 0-16-7.2-16-16zm0 64c0-8.8 7.2-16 16-16h128c8.8 0 16 7.2 16 16s-7.2 16-16 16H192c-8.8 0-16-7.2-16-16z"/>
                </svg>
              </button>
              <button className="p-2 bg-gray-100 hover:bg-gray-200 rounded-lg border border-gray-200" title="Export to Markdown">
                <svg className="w-4 h-4 text-gray-600" fill="currentColor" viewBox="0 0 512 512">
                  <path d="M288 32c0-17.7-14.3-32-32-32s-32 14.3-32 32V274.7l-73.4-73.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l128 128c12.5 12.5 32.8 12.5 45.3 0l128-128c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L288 274.7V32zM64 352c-35.3 0-64 28.7-64 64v32c0 35.3 28.7 64 64 64H448c35.3 0 64-28.7 64-64V416c0-35.3-28.7-64-64-64H346.5l-45.3 45.3c-25 25-65.5 25-90.5 0L165.5 352H64zm368 56a24 24 0 1 1 0 48 24 24 0 1 1 0-48z"/>
                </svg>
              </button>
              <button className="p-2 bg-gray-100 hover:bg-gray-200 rounded-lg border border-gray-200" title="Organize with Tags">
                <svg className="w-4 h-4 text-gray-600" fill="currentColor" viewBox="0 0 640 512">
                  <path d="M0 80V229.5c0 17 6.7 33.3 18.7 45.3l176 176c25 25 65.5 25 90.5 0L418.7 317.3c25-25 25-65.5 0-90.5l-176-176c-12-12-28.3-18.7-45.3-18.7H48C21.5 32 0 53.5 0 80zm112 32a32 32 0 1 1 0 64 32 32 0 1 1 0-64zm160 0V336c0 17 6.7 33.3 18.7 45.3l176 176c25 25 65.5 25 90.5 0L690.7 424.8c25-25 25-65.5 0-90.5l-176-176c-12-12-28.3-18.7-45.3-18.7H320c-17.7 0-32 14.3-32 32z"/>
                </svg>
              </button>
              <button className="p-2 bg-gray-100 hover:bg-gray-200 rounded-lg border border-gray-200" title="Settings">
                <svg className="w-4 h-4 text-gray-600" fill="currentColor" viewBox="0 0 512 512">
                  <path d="M495.9 166.6c3.2 8.7 .5 18.4-6.4 24.6l-43.3 39.4c1.1 8.3 1.7 16.8 1.7 25.4s-.6 17.1-1.7 25.4l43.3 39.4c6.9 6.2 9.6 15.9 6.4 24.6c-4.4 11.9-9.7 23.3-15.8 34.3l-4.7 8.1c-6.6 11-14 21.4-22.1 31.2c-5.9 7.2-15.7 9.6-24.5 6.8l-55.7-17.7c-13.4 10.3-28.2 18.9-44 25.4l-12.5 57.1c-2 9.1-9 16.3-18.2 17.8c-13.8 2.3-28 3.5-42.5 3.5s-28.7-1.2-42.5-3.5c-9.2-1.5-16.2-8.7-18.2-17.8l-12.5-57.1c-15.8-6.5-30.6-15.1-44-25.4L83.1 425.9c-8.8 2.8-18.6 .3-24.5-6.8c-8.1-9.8-15.5-20.2-22.1-31.2l-4.7-8.1c-6.1-11-11.4-22.4-15.8-34.3c-3.2-8.7-.5-18.4 6.4-24.6l43.3-39.4C64.6 273.1 64 264.6 64 256s.6-17.1 1.7-25.4L22.4 191.2c-6.9-6.2-9.6-15.9-6.4-24.6c4.4-11.9 9.7-23.3 15.8-34.3l4.7-8.1c6.6-11 14-21.4 22.1-31.2c5.9-7.2 15.7-9.6 24.5-6.8l55.7 17.7c13.4-10.3 28.2-18.9 44-25.4l12.5-57.1c2-9.1 9-16.3 18.2-17.8C227.3 1.2 241.5 0 256 0s28.7 1.2 42.5 3.5c9.2 1.5 16.2 8.7 18.2 17.8l12.5 57.1c15.8 6.5 30.6 15.1 44 25.4l55.7-17.7c8.8-2.8 18.6-.3 24.5 6.8c8.1 9.8 15.5 20.2 22.1 31.2l4.7 8.1c6.1 11 11.4 22.4 15.8 34.3zM256 336a80 80 0 1 0 0-160 80 80 0 1 0 0 160z"/>
                </svg>
              </button>
              <button className="p-2 bg-red-600 hover:bg-red-700 rounded-lg" title="Logout">
                <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 512 512">
                  <path d="M377.9 105.9L500.7 228.7c7.2 7.2 11.3 17.1 11.3 27.3s-4.1 20.1-11.3 27.3L377.9 406.1c-6.4 6.4-15 9.9-24 9.9c-18.7 0-33.9-15.2-33.9-33.9l0-62.1-128 0c-17.7 0-32-14.3-32-32l0-64c0-17.7 14.3-32 32-32l128 0 0-62.1c0-18.7 15.2-33.9 33.9-33.9c9 0 17.6 3.6 24 9.9zM160 96L96 96c-17.7 0-32 14.3-32 32l0 256c0 17.7 14.3 32 32 32l64 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-64 0c-53 0-96-43-96-96L0 128C0 75 43 32 96 32l64 0c17.7 0 32 14.3 32 32s-14.3 32-32 32z"/>
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Main Chat Area */}
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <MessageSquare className="w-8 h-8 text-blue-600" />
            </div>
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">New Conversation</h2>
            <p className="text-gray-600 mb-8">Start a conversation or search your knowledge base.</p>
          </div>
        </div>

        {/* Bottom Input */}
        <div className="border-t border-gray-200 p-6">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-end space-x-4">
              <button className="p-3 hover:bg-gray-100 rounded-lg" title="Add attachment">
                <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                </svg>
              </button>
              <button className="p-3 hover:bg-gray-100 rounded-lg" title="Upload image">
                <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </button>
              <div className="flex-1 relative">
                <input
                  type="text"
                  placeholder="Ask a question or search knowledge base..."
                  className="w-full px-4 py-3 pr-12 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <button className="absolute right-3 top-1/2 transform -translate-y-1/2 p-2 hover:bg-gray-100 rounded-lg" title="Voice input">
                  <Mic className="w-4 h-4 text-gray-600" />
                </button>
              </div>
              <button className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors">
                Send
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ImprovedAIInterface;
// Cherry-picked from hubzz-altiico/src/components/CollectionBrowser/useCollectionBrowser.ts
// Adjusted: uses ApiAvatar (live API type) instead of static Avatar type.
// Removed: price sort (ApiAvatar has no price field).

import { useState, useMemo, useEffect } from 'react';
import type { ApiAvatar } from '@/lib/avatarApiTypes';
import type { UseBrowserState } from './types';

interface Options {
  avatars: ApiAvatar[];
  initialCollection?: string;
  initialSearch?: string;
  itemsPerPage?: number;
}

export function useCollectionBrowser({
  avatars,
  initialCollection = 'All',
  initialSearch = '',
  itemsPerPage = 60,
}: Options): UseBrowserState {
  const [searchTerm, setSearchTerm] = useState(initialSearch);
  const [selectedCollection, setSelectedCollection] = useState(initialCollection);
  const [sortBy, setSortBy] = useState<'id' | 'collection'>('id');
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    if (initialCollection) setSelectedCollection(initialCollection);
  }, [initialCollection]);

  const collectionList = useMemo(() => {
    return ['All', ...new Set(avatars.map((a) => a.collection_name))];
  }, [avatars]);

  const filteredAvatars = useMemo(() => {
    let list = avatars.filter((a) => {
      const matchSearch =
        a.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        a.collection_name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchCollection =
        selectedCollection === 'All' || a.collection_name === selectedCollection;
      return matchSearch && matchCollection;
    });

    if (sortBy === 'collection') {
      list = [...list].sort((a, b) => a.collection_name.localeCompare(b.collection_name));
    } else {
      list = [...list].sort((a, b) => a.id - b.id);
    }
    return list;
  }, [avatars, searchTerm, selectedCollection, sortBy]);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, selectedCollection]);

  const totalPages = Math.ceil(filteredAvatars.length / itemsPerPage);

  const paginatedAvatars = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredAvatars.slice(start, start + itemsPerPage);
  }, [filteredAvatars, currentPage, itemsPerPage]);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const clearFilters = () => {
    setSearchTerm('');
    setSelectedCollection('All');
    setCurrentPage(1);
  };

  return {
    searchTerm,
    selectedCollection,
    sortBy,
    currentPage,
    filteredAvatars,
    paginatedAvatars,
    totalPages,
    collectionList,
    setSearchTerm,
    setSelectedCollection,
    setSortBy,
    handlePageChange,
    clearFilters,
  };
}

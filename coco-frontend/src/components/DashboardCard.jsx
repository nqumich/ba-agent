import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ArrowUpRight, ArrowDownRight, Activity } from "lucide-react";

/**
 * A reusable card component for displaying dashboard metrics.
 * Now supports trend indicators and dynamic color theming.
 */
const DashboardCard = ({ title, value, trend, trendValue, icon: Icon = Activity, className }) => {
  const isPositive = trend === 'up';
  
  return (
    <Card className={`hover:shadow-md transition-shadow duration-300 ${className}`}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
            <Icon className="h-4 w-4 text-primary" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold mb-1">{value}</div>
        {(trend && trendValue) && (
            <p className={`text-xs flex items-center ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
            {isPositive ? <ArrowUpRight className="mr-1 h-3 w-3" /> : <ArrowDownRight className="mr-1 h-3 w-3" />}
            <span className="font-medium">{trendValue}</span>
            <span className="text-muted-foreground ml-1">vs last month</span>
            </p>
        )}
      </CardContent>
    </Card>
  );
};

export default DashboardCard;
